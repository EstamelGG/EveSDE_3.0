"""公共构建逻辑的离线回归测试；不访问网络或现有 output。"""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from evesde import build_prep, pipeline
from evesde.build_prep import SdeVersionMismatch
from evesde.release import reports as generate_whats_new
from evesde.processors import sde_downloader
from evesde.utils.http_client import RetryableHTTPClient
from evesde.utils import downloads


class HTTPClientTests(unittest.TestCase):
    def setUp(self):
        self.client = RetryableHTTPClient(max_retries=2, retry_delay=0)
        self.addCleanup(self.client.close)

    def test_stream_is_forwarded_without_reading_or_closing(self):
        response = Mock()
        with patch.object(self.client.session, "get", return_value=response) as get:
            self.assertIs(self.client.get("https://example.test", stream=True), response)
        self.assertTrue(get.call_args.kwargs["stream"])
        response.iter_content.assert_not_called()
        response.close.assert_not_called()

    def test_buffered_response_remains_readable(self):
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(b'{"ok": true}')
        response.raw.release_conn = Mock()
        with patch.object(self.client.session, "get", return_value=response):
            result = self.client.get("https://example.test")
        self.assertEqual(result.json(), {"ok": True})
        self.assertEqual(b"".join(result.iter_content(2)), b'{"ok": true}')
        response.raw.release_conn.assert_called_once()

    def test_all_methods_retry_and_close_failed_responses(self):
        for method in ("get", "head", "post"):
            with self.subTest(method=method):
                bad, good = Mock(), Mock()
                bad.status_code = 503
                bad.raise_for_status.side_effect = requests.HTTPError("503")
                good.iter_content.return_value = [b"ok"]
                with patch.object(self.client.session, method, side_effect=[bad, good]) as send:
                    result = getattr(self.client, method)("https://example.test", timeout=7, verify=True)
                self.assertIs(result, good)
                self.assertEqual(send.call_count, 2)
                self.assertEqual(send.call_args.kwargs["timeout"], 7)
                self.assertTrue(send.call_args.kwargs["verify"])
                bad.close.assert_called_once()

    def test_read_error_retries_and_closes_response(self):
        broken, good = Mock(), Mock()
        broken.status_code = 200
        broken.iter_content.side_effect = requests.ConnectionError("interrupted")
        good.iter_content.return_value = [b"complete"]
        with patch.object(self.client.session, "get", side_effect=[broken, good]):
            self.assertEqual(self.client.get("https://example.test")._content, b"complete")
        broken.close.assert_called_once()

    def test_exhausted_retries_raise_original_error(self):
        error = requests.Timeout("offline")
        with patch.object(self.client.session, "get", side_effect=error) as get:
            with self.assertRaises(requests.Timeout) as caught:
                self.client.get("https://example.test")
        self.assertIs(caught.exception, error)
        self.assertEqual(get.call_count, 2)

    def test_invalid_attempt_count(self):
        with self.assertRaises(ValueError):
            RetryableHTTPClient(max_retries=0)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = {"paths": {"sde_zip": str(self.root / "downloads")},
                       "urls": {"sde_download_template": "https://example.test/{build_number}"}}

    def zip_bytes(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("types.jsonl", '{"_key":1}')
        return stream.getvalue()

    def response(self, content):
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(content)
        response.raw.release_conn = Mock()
        return response

    def test_crc_corruption_is_rejected(self):
        target = sde_downloader.archive_path(self.config, "123.01")
        target.parent.mkdir()
        target.write_bytes(self.zip_bytes().replace(b'{"_key":1}', b'{"_key":2}'))
        with self.assertRaises(zipfile.BadZipFile):
            downloads.validate_zip(target)

    def test_download_creates_parent_validates_and_closes(self):
        payload = self.zip_bytes()
        response = self.response(payload)
        with patch.object(downloads, "get", return_value=response) as get:
            ok, target = sde_downloader.download_sde(self.config, "123.01")
        self.assertTrue(ok)
        self.assertEqual(target.read_bytes(), payload)
        self.assertEqual(get.call_args.args[0], "https://example.test/123")
        response.raw.release_conn.assert_called_once()
        self.assertFalse(target.with_suffix(".zip.part").exists())

    def test_invalid_download_preserves_previous_file(self):
        target = sde_downloader.archive_path(self.config, "123")
        target.parent.mkdir()
        original = self.zip_bytes()
        target.write_bytes(original)
        response = self.response(b"invalid archive")
        with patch.object(downloads, "get", return_value=response):
            self.assertEqual(sde_downloader.download_sde(self.config, "123"), (False, None))
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse(target.with_suffix(".zip.part").exists())
        response.raw.release_conn.assert_called_once()

    def test_interrupted_download_cleans_partial_file(self):
        response = self.response(b"")
        def interrupted(**kwargs):
            yield b"partial"
            raise requests.ConnectionError("interrupted")
        response.iter_content = interrupted
        with patch.object(downloads, "get", return_value=response):
            self.assertEqual(sde_downloader.download_sde(self.config, "123"), (False, None))
        self.assertEqual(list((self.root / "downloads").iterdir()), [])
        response.raw.release_conn.assert_called_once()


class OtherDownloadTests(unittest.TestCase):
    def test_missing_config_does_not_mask_original_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(generate_whats_new.download_and_extract_jsonl({}, "123", Path(directory)))


class PipelineTests(unittest.TestCase):
    def test_order_and_accepted_success_values(self):
        calls = []
        config = {}
        def processor(value):
            def run(received):
                self.assertIs(received, config)
                calls.append(value)
                return value
            return run
        steps = [("a", str(i), processor(value)) for i, value in enumerate((None, True, 1))]
        with patch.object(pipeline, "PIPELINE_STEPS", steps):
            pipeline.run_pipeline(config)
        self.assertEqual(calls, [None, True, 1])

    def test_failure_stops_following_steps(self):
        later = Mock()
        for result in (False, 0, "", []):
            with self.subTest(result=result):
                with patch.object(pipeline, "PIPELINE_STEPS", [("a", "失败步骤", lambda _: result), ("a", "后续", later)]):
                    with self.assertRaisesRegex(RuntimeError, "失败步骤处理失败"):
                        pipeline.run_pipeline({})
        later.assert_not_called()

    def test_exception_has_step_name_and_cause(self):
        cause = ValueError("broken")
        with self.assertRaisesRegex(RuntimeError, "测试步骤") as caught:
            pipeline.execute_processor(Mock(side_effect=cause), "测试步骤", {})
        self.assertIs(caught.exception.__cause__, cause)

    def test_callback_contract_is_preserved(self):
        callback, fn = Mock(), Mock()
        with patch.object(pipeline, "PIPELINE_STEPS", [("a", "步骤", fn)]):
            pipeline.run_pipeline({}, on_step=callback)
        callback.assert_called_once_with("a", "步骤", fn)
        fn.assert_not_called()


class SdeVersionInfoTests(unittest.TestCase):
    config = {"urls": {"sde_binary": "https://example.test/binary", "sde_update": "https://example.test/update"}}

    def response(self, payload):
        response = Mock()
        response.text = json.dumps(payload)
        return response

    def test_mismatch_raises_and_carries_update_version(self):
        with patch("evesde.build_prep.get", side_effect=[self.response({"build_number": 124}),
                                                         self.response({"buildNumber": 123, "releaseDate": "2026-10-07"})]):
            with self.assertRaises(SdeVersionMismatch) as caught:
                build_prep.fetch_latest_sde_info(self.config)
        self.assertEqual(caught.exception.info["build_number"], 123)
        self.assertEqual(caught.exception.info["binary_build_number"], 124)

    def test_mismatch_returns_none_for_legacy_callers(self):
        with patch("evesde.build_prep.get", side_effect=[self.response({"build_number": 124}),
                                                         self.response({"buildNumber": 123})]):
            self.assertIsNone(build_prep.get_latest_sde_info(self.config))

    def test_skip_version_check_uses_update_version(self):
        with patch("evesde.build_prep.get", side_effect=[self.response({"build_number": 124}),
                                                         self.response({"buildNumber": 123, "releaseDate": "2026-10-07"})]):
            info = build_prep.fetch_latest_sde_info(self.config, skip_version_check=True)
        self.assertEqual(info["build_number"], 123)


if __name__ == "__main__":
    unittest.main()

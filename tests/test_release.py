"""版本选择、附件契约、同次构建复用和历史同步的离线集成测试。"""
from dataclasses import replace
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

import requests

from evesde.github import GitHub, output
from evesde.maintenance import clean_artifacts
from evesde.release import assets, history, reports
from evesde.release.baseline import ReleaseBaseline
from evesde.release.plan import BuildPlan, create_plan


def plan(**changes):
    base = BuildPlan("123", "123", "0", "2026-10-07T00:00:00Z", "sde", "owner/repo", None,
                     {"build_number": 123})
    return replace(base, **changes)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.info = patch("evesde.release.plan.get_latest_sde_info", return_value={
            "build_number": 123, "release_date": "2026-10-07", "key": "sde", "client_data": {"build_number": 123}
        }).start()
        self.github = patch("evesde.release.plan.GitHub").start().return_value
        self.github.release.return_value = None
        self.github.latest_release.return_value = None
        self.environment = patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}).start()
        self.addCleanup(patch.stopall)

    def test_first_release(self):
        result = create_plan({})
        self.assertTrue(result.should_build)
        self.assertEqual(result.final_build_number, "123")
        self.assertIsNone(result.previous_release)

    def test_existing_release_skips_build_and_baseline_query(self):
        self.github.release.return_value = {"id": 1}
        result = create_plan({})
        self.assertFalse(result.should_build)
        self.github.latest_release.assert_not_called()

    def test_patch_uses_first_free_number_including_drafts(self):
        self.github.release.return_value = {"id": 1}
        self.github.pages.return_value = [{"tag_name": "sde-build-123.01", "draft": True},
                                         {"tag_name": "sde-build-123.03"}]
        result = create_plan({}, patch=True)
        self.assertEqual((result.final_build_number, result.patch_version), ("123.02", "2"))

    def test_patch_limit_fails(self):
        self.github.release.return_value = {"id": 1}
        self.github.pages.return_value = [{"tag_name": f"sde-build-123.{i:02d}"} for i in range(1, 100)]
        with self.assertRaisesRegex(RuntimeError, "99"):
            create_plan({}, patch=True)

    def test_debug_does_not_select_patch_or_skip_existing_build(self):
        result = create_plan({}, patch=True, debug=True)
        self.assertTrue(result.debug and result.should_build)
        self.assertEqual(result.final_build_number, "123")
        self.github.release.assert_not_called()

    def test_version_mismatch_stops_before_github(self):
        self.info.return_value = None
        with self.assertRaises(RuntimeError):
            create_plan({})
        self.github.release.assert_not_called()

    def test_plan_round_trip_preserves_pinned_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "plan.json"
            expected = create_plan({})
            expected.save(target)
            self.assertEqual(BuildPlan.load(target), expected)

    def test_inconsistent_patch_is_rejected(self):
        with self.assertRaises(ValueError):
            plan(final_build_number="123.01", patch_version="2")


class GitHubTests(unittest.TestCase):
    @staticmethod
    def baseline_release(version, **fields):
        return {"tag_name": f"sde-build-{version}", "assets": [
            {"name": name, "state": "uploaded", "url": f"https://example.test/{name}"}
            for name in ("sde.zip", "icons.zip", "metadata.json")], **fields}

    def test_valid_latest_returns_without_pagination(self):
        github = GitHub("owner/repo")
        latest = self.baseline_release("123")
        with patch.object(github, "json", return_value=latest) as query, patch.object(github, "pages") as pages:
            self.assertEqual(github.latest_release(), latest)
        query.assert_called_once_with("releases/latest", missing_ok=True)
        pages.assert_not_called()

    def test_latest_404_falls_back_to_release_list(self):
        github = GitHub("owner/repo")
        response = requests.Response()
        response.status_code = 404
        previous = self.baseline_release("122")
        with patch("evesde.github.get", side_effect=requests.HTTPError(response=response)), patch.object(github, "pages", return_value=[previous]) as pages:
            self.assertEqual(github.latest_release(), previous)
        pages.assert_called_once_with("releases")

    def test_baseline_uses_versions_across_pages_without_latest(self):
        github = GitHub("owner/repo")
        newest = self.baseline_release("123.10", id=1)
        first = [self.baseline_release("123.09", id=999),
                 self.baseline_release("123"), self.baseline_release("122.99")]
        first += [{"tag_name": "unrelated"}] * 97
        with patch.object(github, "json", side_effect=[None, first, [newest]]) as query:
            self.assertEqual(github.latest_release(), newest)
        self.assertEqual([call.args[0] for call in query.call_args_list],
                         ["releases/latest", "releases?per_page=100&page=1", "releases?per_page=100&page=2"])

    def test_baseline_skips_unusable_releases(self):
        github = GitHub("owner/repo")
        previous = self.baseline_release("123")
        incomplete = self.baseline_release("124")
        incomplete["assets"][0]["state"] = "starter"
        records = [previous, incomplete, self.baseline_release("125", assets=[]),
                   self.baseline_release("126", draft=True),
                   self.baseline_release("127", prerelease=True),
                   self.baseline_release("128", tag_name="other-project-128")]
        with patch.object(github, "json", return_value=incomplete), patch.object(github, "pages", return_value=records):
            self.assertEqual(github.latest_release(), previous)

    def test_baseline_distinguishes_first_release_from_broken_history(self):
        github = GitHub("owner/repo")
        with patch.object(github, "json", return_value=None), patch.object(github, "pages", return_value=[]):
            self.assertIsNone(github.latest_release())
        with patch.object(github, "json", return_value=None), patch.object(github, "pages", return_value=[self.baseline_release("123", assets=[])]):
            with self.assertRaisesRegex(RuntimeError, "基线附件"):
                github.latest_release()

    def test_baseline_listing_errors_are_not_first_release(self):
        github = GitHub("owner/repo")
        for status in (404, 401, 403, 500):
            response = requests.Response()
            response.status_code = status
            with self.subTest(status=status), patch("evesde.github.get", side_effect=requests.HTTPError(response=response)):
                with self.assertRaises(requests.HTTPError):
                    github.latest_release()

    def test_only_404_means_missing(self):
        for status in (404, 401, 403, 500):
            with self.subTest(status=status):
                response = requests.Response()
                response.status_code = status
                error = requests.HTTPError(response=response)
                with patch("evesde.github.get", side_effect=error):
                    if status == 404:
                        self.assertIsNone(GitHub("owner/repo").release("123"))
                    else:
                        with self.assertRaises(requests.HTTPError):
                            GitHub("owner/repo").release("123")

    def test_pagination_does_not_drop_later_pages(self):
        github = GitHub("owner/repo")
        first = [{"id": i} for i in range(100)]
        with patch.object(github, "json", side_effect=[first, [{"id": 100}]]) as query:
            self.assertEqual(len(list(github.pages("releases"))), 101)
        self.assertIn("page=2", query.call_args.args[0])

    def test_multiline_outputs_allow_eof_in_value(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(target)}):
                output("files", "a\nEOF\nb")
                output("ok", True)
            text = target.read_text()
            marker = text.splitlines()[0].split("<<")[1]
            self.assertIn(f"a\nEOF\nb\n{marker}\n", text)
            self.assertIn("\ntrue\n", text)

    def test_baseline_downloads_attachment_once(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = ReleaseBaseline("owner/repo", {"assets": [{"name": "icons.zip", "url": "https://example.test"}]}, Path(directory))
            with patch.object(baseline.github, "download_asset", return_value=Path(directory) / "icons.zip") as download:
                self.assertEqual(baseline.asset("icons.zip"), baseline.asset("icons.zip"))
            download.assert_called_once()

    def test_artifact_cleanup_keeps_newest_and_recent(self):
        records = [{"id": 1, "created_at": "2026-10-07T00:00:00Z"},
                   {"id": 2, "created_at": "2026-10-06T00:00:00Z"},
                   {"id": 3, "created_at": "2026-09-01T00:00:00Z"}]
        with patch("evesde.maintenance.GitHub") as factory:
            factory.return_value.pages.return_value = records
            deleted = clean_artifacts("owner/repo", keep=1, days=5, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
        self.assertEqual(deleted, [3])
        factory.return_value.delete_artifact.assert_called_once_with(3)


class ReleaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.patch_root = patch.object(assets, "PROJECT_ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.config = {"paths": {"sde_output": "output/sde", "icons_output": "output/icons",
                                 "release_output": "output/release", "item_detail_en": "output/item_detail/en",
                                 "item_detail_zh": "output/item_detail/zh"}}
        for relative in self.config["paths"].values():
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        self.sde = self.root / "output/sde"
        (self.sde / "db").mkdir()
        # 高熵数据使测试走真实的大小校验、SQLite 校验、ZIP 和 tar 打包流程。
        payload = random.Random(123).randbytes(6 * 1024 * 1024)
        with closing(sqlite3.connect(self.sde / "db/item_db.sqlite")) as conn:
            conn.execute("CREATE TABLE types (type_id INTEGER PRIMARY KEY, data BLOB)")
            conn.execute("INSERT INTO types VALUES (1, ?)", (payload,))
            conn.commit()
        with zipfile.ZipFile(self.sde / "texts.zip", "w") as archive:
            archive.writestr("texts.json", '{"0":"text"}')
        with zipfile.ZipFile(self.root / "output/icons/icons.zip", "w") as archive:
            archive.writestr("1.png", payload[:2 * 1024 * 1024])
        for lang in ("en", "zh"):
            (self.root / f"output/item_detail/{lang}/item_1.json").write_text('{"type_id":1}')
        self.baseline = ReleaseBaseline("owner/repo", None, self.root / "baseline")

    def test_first_release_packaging_and_history_commit(self):
        compare = self.root / "output/release/release_compare_123.md"
        compare.write_text("first release")
        result = assets.prepare_release(self.config, plan(), self.baseline)
        metadata = json.loads((self.root / "output/release/metadata.json").read_text())
        self.assertEqual(metadata["icon_version"], 1)
        self.assertEqual(metadata["build_number"], 123)
        self.assertEqual(metadata["sde_sha256"], assets.sha256_file(self.root / "output/release/sde.zip"))
        with zipfile.ZipFile(self.root / "output/release/sde.zip") as archive:
            self.assertIn("db/item_db.sqlite", archive.namelist())
            self.assertIn("texts.zip", archive.namelist())
        with tarfile.open(self.root / "output/release/sde-build-123-all.tar.gz") as archive:
            self.assertEqual(set(archive.getnames()), {"sde.zip", "icons.zip", "metadata.json"})
        self.assertTrue(all((self.root / file).is_file() for file in result["files"]))
        checkout = self.root / "repo"
        subprocess.run(["git", "init", "-b", "main", str(checkout)], check=True, capture_output=True)
        manifest = self.root / "output/release/release-manifest.json"
        with patch.object(history, "PROJECT_ROOT", self.root):
            commit = history.sync_history(manifest, checkout)
            self.assertEqual(history.sync_history(manifest, checkout), commit)
        self.assertEqual((checkout / "output/item_detail/en/item_1.json").read_text(), '{"type_id":1}')
        self.assertEqual(len(list((checkout / "history").glob("*.md"))), 1)
        self.assertIn("history/release_compare_123_", (self.root / result["notes"]).read_text())

    def test_json_report_is_only_inside_sde_zip(self):
        report = self.root / "output/whats_new/whats_new_122_123.md"
        report.parent.mkdir(parents=True)
        report.write_text("report")
        json_report = report.with_name("whats_new.json")
        json_report.write_text('{"schema_version":1,"attribute_changes":{}}')
        result = assets.prepare_release(self.config, plan(), self.baseline, report)
        self.assertFalse(any(name.endswith("whats_new.json") for name in result["files"]))
        with zipfile.ZipFile(self.root / "output/release/sde.zip") as archive:
            self.assertEqual(archive.read("whats_new.json"), json_report.read_bytes())
        with tarfile.open(self.root / "output/release/sde-build-123-all.tar.gz") as archive:
            self.assertNotIn(json_report.name, archive.getnames())
        self.assertIn(json_report.name, (self.root / result["notes"]).read_text())
        checkout = self.root / "repo"
        subprocess.run(["git", "init", "-b", "main", str(checkout)], check=True, capture_output=True)
        with patch.object(history, "PROJECT_ROOT", self.root):
            history.sync_history(self.root / "output/release/release-manifest.json", checkout)
        self.assertFalse((checkout / "output/whats_new" / json_report.name).exists())
        self.assertTrue((checkout / "output/whats_new" / report.name).is_file())

    def test_markdown_without_json_cannot_be_published(self):
        report = self.root / "whats_new_122_123.md"
        report.write_text("report")
        with self.assertRaisesRegex(FileNotFoundError, "未完整生成"):
            assets.prepare_release(self.config, plan(), self.baseline, report)

    def test_empty_details_prevent_packaging(self):
        (self.root / "output/item_detail/zh/item_1.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "物品详情"):
            assets.prepare_release(self.config, plan(), self.baseline)

    def test_debug_manifest_cannot_sync_history(self):
        manifest = self.root / "manifest.json"
        manifest.write_text('{"debug":true}')
        with self.assertRaisesRegex(ValueError, "调试"):
            history.sync_history(manifest, self.root / "repo")


class ReportTests(unittest.TestCase):
    def test_patch_report_reuses_current_jsonl(self):
        baseline = Mock(release={"tag_name": "sde-build-123"}, directory=Path("unused"))
        baseline.asset.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"paths": {"sde_input": str(root / "jsonl"), "whats_new": str(root / "reports"),
                                 "icons_output": str(root / "icons")}}
            (root / "jsonl").mkdir()
            for name in reports.REQUIRED_JSONL:
                (root / "jsonl" / f"{name}.jsonl").touch()
            def analyze(config, old, current, output, **kwargs):
                self.assertEqual(old, current)
                output.write_text("report")
                output.with_name("whats_new.json").write_text('{"schema_version":1}')
                self.assertEqual(kwargs["old_version"], "123")
                self.assertEqual(kwargs["new_version"], "123.01")
                return True
            with patch.object(reports, "download_and_extract_jsonl") as download, patch.object(reports.item_changes_analyzer, "main", side_effect=analyze):
                result = reports.generate_report(config, plan(final_build_number="123.01", patch_version="1"), baseline)
            download.assert_not_called()
            self.assertEqual(result.name, "whats_new_123_123.01.md")

    def test_report_generation_requires_json_companion(self):
        baseline = Mock(release={"tag_name": "sde-build-123"}, directory=Path("unused"))
        baseline.asset.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"paths": {"sde_input": str(root), "whats_new": str(root / "reports"),
                                 "icons_output": str(root / "icons")}}
            for name in reports.REQUIRED_JSONL:
                (root / f"{name}.jsonl").touch()
            def markdown_only(config, old, current, output, **kwargs):
                output.write_text("report")
                return True
            with patch.object(reports.item_changes_analyzer, "main", side_effect=markdown_only):
                with self.assertRaisesRegex(RuntimeError, "生成失败"):
                    reports.generate_report(config, plan(), baseline)

    def test_icon_version_only_increments_on_content_change(self):
        baseline = Mock()
        baseline.metadata.return_value = {"icon_sha256": "same", "icon_version": 4}
        self.assertEqual(assets.next_icon_version(baseline, "same"), 4)
        self.assertEqual(assets.next_icon_version(baseline, "different"), 5)


if __name__ == "__main__":
    unittest.main()

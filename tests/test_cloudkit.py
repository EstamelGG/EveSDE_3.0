import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
import base64

from evesde.cloudkit import CloudKit, latest_release, sync, version


class CloudKitTests(unittest.TestCase):
    def test_http_error_includes_redacted_cloudkit_diagnostics(self):
        client = object.__new__(CloudKit)
        client.path = '/database/1/iCloud.test/development/public/'
        client.key_id = 'test-key'
        client.key = ec.generate_private_key(ec.SECP256R1())
        response = Mock(ok=False, status_code=400)
        response.json.return_value = {
            'serverErrorCode': 'BAD_REQUEST',
            'reason': 'Invalid field type ASSET https://example.com/?receipt=secret',
            'uuid': 'request-id', 'receipt': 'never-log-this'}
        with patch('evesde.cloudkit.requests.post', return_value=response):
            with self.assertRaises(RuntimeError) as caught:
                client.call('records/modify', {})
        message = str(caught.exception)
        self.assertIn('BAD_REQUEST', message)
        self.assertIn('Invalid field type ASSET', message)
        self.assertIn('request-id', message)
        self.assertNotIn('receipt=secret', message)
        self.assertNotIn('never-log-this', message)

    def test_signature_covers_exact_request_body_and_path(self):
        client = object.__new__(CloudKit)
        client.path = '/database/1/iCloud.test/development/public/'
        client.key_id = 'test-key'
        client.key = ec.generate_private_key(ec.SECP256R1())
        response = Mock(ok=True)
        response.json.return_value = {'records': []}
        with patch('evesde.cloudkit.requests.post', return_value=response) as post:
            client.call('records/query', {'query': {'recordType': 'SDE_v3'}})
        kwargs = post.call_args.kwargs
        headers = kwargs['headers']
        message = ':'.join([headers['X-Apple-CloudKit-Request-ISO8601Date'],
                            base64.b64encode(hashlib.sha256(kwargs['data']).digest()).decode(),
                            client.path + 'records/query'])
        client.key.public_key().verify(base64.b64decode(headers['X-Apple-CloudKit-Request-SignatureV1']),
                                       message.encode(), ec.ECDSA(hashes.SHA256()))

    def test_success_publishes_assets_before_creating_record_and_reads_back(self):
        github, cloudkit = Mock(), Mock()
        metadata = {'build_number': 10, 'patch_number': 3,
                    'sde_sha256': hashlib.sha256(b'sde').hexdigest(),
                    'icon_sha256': hashlib.sha256(b'icons').hexdigest()}
        text = json.dumps(metadata)
        github.pages.return_value = [{'tag_name': 'sde-build-10.03', 'assets': [
            {'name': name, 'state': 'uploaded'} for name in ('metadata.json', 'sde.zip', 'icons.zip')]}]
        def download(asset, path):
            path.write_bytes(text.encode() if asset['name'] == 'metadata.json'
                             else asset['name'].split('.')[0].encode())
            return path
        github.download_asset.side_effect = download
        cloudkit.latest.return_value = (10, 2)
        cloudkit.upload.side_effect = lambda name, field, path: {'size': path.stat().st_size, 'fileChecksum': field}
        saved = {}
        def call(operation, payload):
            if operation == 'records/modify':
                self.assertEqual(cloudkit.upload.call_count, 2)
                saved.update(payload['operations'][0]['record'])
                for field in saved['fields'].values():
                    self.assertEqual(set(field), {'value'})
                return {'records': [saved]}
            self.assertEqual(operation, 'records/lookup')
            return {'records': [saved]}
        cloudkit.call.side_effect = call
        self.assertEqual(sync(github, cloudkit, '1.14'), 'Published sde-build-10.03')
        self.assertEqual(saved['fields']['sde_version']['value'], 10.0)

    def test_numeric_release_order_ignores_drafts_and_prereleases(self):
        github = Mock()
        github.pages.return_value = [
            {'tag_name': 'sde-build-9.99'}, {'tag_name': 'sde-build-10'},
            {'tag_name': 'sde-build-10.01'},
            {'tag_name': 'sde-build-11', 'draft': True},
            {'tag_name': 'sde-build-12', 'prerelease': True}]
        self.assertEqual(latest_release(github)[0], (10, 1))

    def test_pagination_includes_patch_versions(self):
        client = object.__new__(CloudKit)
        def record(patch):
            return {'fields': {'metadata': {'value': json.dumps({'build_number': 10, 'patch_number': patch})},
                               'sde_version': {'value': 10.0}}}
        client.call = Mock(side_effect=[{'records': [record(0)], 'continuationMarker': 'next'},
                                        {'records': [record(3)]}])
        self.assertEqual(client.latest(), (10, 3))
        self.assertEqual(client.call.call_args.args[1]['continuationMarker'], 'next')

    def test_skip_equal_version_does_not_download_or_upload(self):
        github, cloudkit = Mock(), Mock()
        github.pages.return_value = [{'tag_name': 'sde-build-10.03'}]
        cloudkit.latest.return_value = (10, 3)
        self.assertIn('skipped', sync(github, cloudkit, '1.14'))
        github.download_asset.assert_not_called()
        cloudkit.upload.assert_not_called()

    def test_check_only_does_not_download(self):
        github, cloudkit = Mock(), Mock()
        github.pages.return_value = [{'tag_name': 'sde-build-10.03'}]
        cloudkit.latest.return_value = (10, 2)
        self.assertIn('check-only', sync(github, cloudkit, '1.14', True))
        github.download_asset.assert_not_called()

    def test_hash_mismatch_prevents_cloud_writes(self):
        github, cloudkit = Mock(), Mock()
        github.pages.return_value = [{'tag_name': 'sde-build-10.03', 'assets': [
            {'name': name, 'state': 'uploaded'} for name in ('metadata.json', 'sde.zip', 'icons.zip')]}]
        cloudkit.latest.return_value = (10, 2)
        def download(asset, path):
            if asset['name'] == 'metadata.json':
                path.write_text(json.dumps({'build_number': 10, 'patch_number': 3,
                                           'sde_sha256': hashlib.sha256(b'expected').hexdigest()}))
            else:
                path.write_bytes(b'corrupt')
            return path
        github.download_asset.side_effect = download
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            sync(github, cloudkit, '1.14')
        cloudkit.upload.assert_not_called()
        cloudkit.call.assert_not_called()

    def test_invalid_version_fails_closed(self):
        for metadata in ({'build_number': 10, 'patch_number': 100},
                         {'build_number': True}, {'build_number': 10.5}):
            with self.assertRaises(ValueError):
                version(metadata)


if __name__ == '__main__':
    unittest.main()

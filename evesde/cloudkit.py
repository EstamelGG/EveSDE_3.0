"""Independent GitHub Release -> CloudKit public database publisher."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from evesde.github import GitHub


def error_detail(result):
    """Expose useful diagnostics without asset receipts or signed URLs."""
    parts = []
    for key in ('serverErrorCode', 'reason', 'uuid'):
        value = result.get(key)
        if not isinstance(value, str):
            continue
        value = re.sub(r'https?://\S+', '[URL redacted]', value)
        value = re.sub(r'[A-Za-z0-9_+/=-]{48,}', '[token redacted]', value)
        parts.append(f'{key}={value[:500]}')
    return '; '.join(parts)


def version(metadata):
    build, patch = metadata['build_number'], metadata.get('patch_number', 0)
    if isinstance(build, bool) or isinstance(patch, bool):
        raise ValueError('Invalid boolean version')
    if str(build) != str(int(build)) or str(patch) != str(int(patch)):
        raise ValueError('Version must contain integers')
    if int(build) <= 0 or not 0 <= int(patch) <= 99:
        raise ValueError('Invalid build or patch number')
    return int(build), int(patch)


def latest_release(github):
    """Select by numeric SDE version, regardless of GitHub's latest flag."""
    candidates = []
    for release in github.pages('releases'):
        match = re.fullmatch(r'sde-build-([0-9]+)(?:\.([0-9]{2}))?', release.get('tag_name', ''))
        if match and not release.get('draft') and not release.get('prerelease'):
            candidates.append(((int(match[1]), int(match[2] or 0)), release))
    if not candidates:
        raise RuntimeError('No official SDE Release found')
    return max(candidates, key=lambda item: item[0])


class CloudKit:
    def __init__(self, container, environment):
        self.path = f'/database/1/{container}/{environment}/public/'
        self.key_id = os.environ['CLOUDKIT_KEY_ID']
        self.key = serialization.load_pem_private_key(
            os.environ['CLOUDKIT_PRIVATE_KEY'].encode(), password=None)
        if not isinstance(self.key, ec.EllipticCurvePrivateKey) or not isinstance(self.key.curve, ec.SECP256R1):
            raise ValueError('CloudKit requires a P-256 EC private key')

    def call(self, operation, payload):
        body = json.dumps(payload, separators=(',', ':')).encode()
        date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        path = self.path + operation
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        signature = self.key.sign(f'{date}:{digest}:{path}'.encode(), ec.ECDSA(hashes.SHA256()))
        response = requests.post('https://api.apple-cloudkit.com' + path, data=body, headers={
            'Content-Type': 'application/json',
            'X-Apple-CloudKit-Request-KeyID': self.key_id,
            'X-Apple-CloudKit-Request-ISO8601Date': date,
            'X-Apple-CloudKit-Request-SignatureV1': base64.b64encode(signature).decode(),
        }, timeout=(30, 180))
        try:
            result = response.json()
        except ValueError:
            result = {}
        if not isinstance(result, dict):
            result = {}
        if not response.ok:
            detail = error_detail(result)
            raise RuntimeError(f'CloudKit {operation}: HTTP {response.status_code}'
                               + (f'; {detail}' if detail else ''))
        for item in [result, *result.get('records', [])]:
            if item.get('serverErrorCode'):
                raise RuntimeError(f'CloudKit {operation}: {error_detail(item)}')
        return result

    def latest(self):
        payload = {'query': {'recordType': 'SDE_v3'},
                   'desiredKeys': ['metadata', 'sde_version'], 'resultsLimit': 200}
        versions = []
        while True:
            result = self.call('records/query', payload)
            if not isinstance(result.get('records'), list):
                raise RuntimeError('CloudKit query missing records')
            for record in result['records']:
                fields = record['fields']
                metadata = json.loads(fields['metadata']['value'])
                value = version(metadata)
                if float(fields['sde_version']['value']) != value[0]:
                    raise ValueError('CloudKit metadata and sde_version disagree')
                versions.append(value)
            cursor = result.get('continuationMarker')
            if not cursor:
                return max(versions, default=(0, 0))
            payload['continuationMarker'] = cursor

    def upload(self, name, field, file):
        result = self.call('assets/upload', {'tokens': [{
            'recordName': name, 'recordType': 'SDE_v3', 'fieldName': field}]})
        url = result['tokens'][0]['url']
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            raise ValueError('CloudKit returned an invalid upload URL')
        with file.open('rb') as stream:
            response = requests.post(url, data=stream,
                                     headers={'Content-Type': 'application/octet-stream'},
                                     timeout=(30, 900), allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError(f'CloudKit asset upload: HTTP {response.status_code}')
        asset = response.json()['singleFile']
        if int(asset['size']) != file.stat().st_size:
            raise ValueError('Uploaded asset size mismatch')
        return asset


def sync(github, cloudkit, minimum_app_version, check_only=False):
    target, release = latest_release(github)
    current = cloudkit.latest()
    print(f'CloudKit: {current[0]}.{current[1]:02d}; GitHub: {target[0]}.{target[1]:02d}')
    if target <= current:
        return 'Already current; skipped'
    if check_only:
        return 'Newer Release available; check-only mode'
    assets = {a['name']: a for a in release.get('assets', []) if a.get('state') == 'uploaded'}
    required = {'metadata.json', 'sde.zip', 'icons.zip'}
    if not required <= assets.keys():
        raise ValueError('Newest Release is missing required assets')
    with tempfile.TemporaryDirectory(prefix='evesde-cloudkit-') as directory:
        root = Path(directory)
        github.download_asset(assets['metadata.json'], root / 'metadata.json')
        metadata_text = (root / 'metadata.json').read_text(encoding='utf-8')
        metadata = json.loads(metadata_text)
        if version(metadata) != target:
            raise ValueError('Release tag and metadata version disagree')
        for field, hash_key in [('sde', 'sde_sha256'), ('icons', 'icon_sha256')]:
            path = github.download_asset(assets[field + '.zip'], root / (field + '.zip'))
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != metadata[hash_key]:
                raise ValueError(f'{field} SHA256 mismatch')
        # Recheck after downloads; never publish over a newer version.
        if target <= cloudkit.latest():
            return 'CloudKit advanced during download; skipped'
        name = release['tag_name']
        fields = {
            'metadata': {'value': metadata_text},
            'sde_version': {'value': float(target[0])},
            'minimum_app_version': {'value': minimum_app_version},
        }
        for field in ('icons', 'sde'):
            # Existing schema determines the type. Use the documented Asset
            # receipt dictionary rather than a response-side type discriminator.
            fields[field] = {'value': cloudkit.upload(name, field, root / (field + '.zip'))}
        cloudkit.call('records/modify', {'operations': [{'operationType': 'create', 'record': {
            'recordName': name, 'recordType': 'SDE_v3', 'fields': fields}}]})
        result = cloudkit.call('records/lookup', {'records': [{'recordName': name}]})
        saved = result['records'][0]['fields']
        if any(saved[key]['value'] != fields[key]['value'] for key in ('metadata', 'sde_version', 'minimum_app_version')):
            raise ValueError('CloudKit read-back metadata mismatch')
        for field in ('icons', 'sde'):
            for key in ('size', 'fileChecksum'):
                if saved[field]['value'][key] != fields[field]['value'][key]:
                    raise ValueError('CloudKit read-back asset mismatch')
    return f'Published {release["tag_name"]}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=['development', 'production'], default='development')
    parser.add_argument('--container', default='iCloud.secgg.EVE-Nexus')
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY', 'EstamelGG/EveSDE_3.0'))
    parser.add_argument('--minimum-app-version', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+(?:\.\d+)*', args.minimum_app_version):
        parser.error('minimum-app-version must be a dotted numeric version')
    result = sync(GitHub(args.repository), CloudKit(args.container, args.environment),
                  args.minimum_app_version, args.check_only)
    print(result)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(f'CloudKit ({args.environment}): {result}\n')


if __name__ == '__main__':
    main()

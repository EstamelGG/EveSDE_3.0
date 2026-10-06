"""GitHub 集成边界：API、附件下载和 Actions 输出。"""
from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote

import requests

from evesde.utils.http_client import get
from evesde.utils.downloads import download_file


def output(name: str, value) -> None:
    value = str(value).lower() if isinstance(value, bool) else str(value)
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        delimiter = f"evesde_{uuid4().hex}"
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def repository_name(config: dict) -> str:
    repository = (os.environ.get("GITHUB_REPOSITORY") or config.get("github_repo", "")).strip()
    if len(repository.split("/")) != 2 or not all(repository.split("/")):
        raise ValueError("必须配置 owner/repo 格式的 github_repo 或 GITHUB_REPOSITORY")
    return repository


class GitHub:
    def __init__(self, repository: str):
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"

    def headers(self, accept="application/vnd.github+json") -> dict:
        headers = {"Accept": accept, "User-Agent": "EveSDE/3.0"}
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def json(self, endpoint: str, *, missing_ok=False):
        try:
            return get(f"{self.base}/{endpoint}", headers=self.headers(), timeout=30).json()
        except requests.HTTPError as exc:
            if missing_ok and exc.response is not None and exc.response.status_code == 404:
                return None
            raise

    def pages(self, endpoint: str, key: str | None = None):
        page = 1
        while True:
            separator = "&" if "?" in endpoint else "?"
            data = self.json(f"{endpoint}{separator}per_page=100&page={page}")
            items = data[key] if key else data
            if not isinstance(items, list):
                raise ValueError(f"GitHub {endpoint} 未返回列表")
            yield from items
            if len(items) < 100:
                return
            page += 1

    def release(self, build_number: str):
        tag = quote(f"sde-build-{build_number}", safe="")
        return self.json(f"releases/tags/{tag}", missing_ok=True)

    def latest_release(self):
        """优先使用 latest，不可用时分页按数据版本选择完整基线。"""
        required = {"sde.zip", "icons.zip", "metadata.json"}

        def version_of(release):
            if not release or release.get("draft") or release.get("prerelease"):
                return None
            match = re.fullmatch(r"sde-build-([0-9]+)(?:\.([0-9]{2}))?",
                                 release.get("tag_name", ""))
            return (int(match[1]), int(match[2] or 0)) if match else None

        def complete(release):
            available = {asset.get("name") for asset in release.get("assets", [])
                         if asset.get("state") == "uploaded"
                         and (asset.get("url") or asset.get("browser_download_url"))}
            return required <= available

        latest = self.json("releases/latest", missing_ok=True)
        if version_of(latest) is not None and complete(latest):
            return latest

        candidates, incomplete = [], []
        for release in self.pages("releases"):
            version = version_of(release)
            if version is None:
                continue
            if not complete(release):
                incomplete.append(release["tag_name"])
                continue
            candidates.append((version, release))
        if candidates:
            return max(candidates, key=lambda entry: entry[0])[1]
        if incomplete:
            raise RuntimeError("已有 SDE Release 均缺少完整的基线附件，无法比较："
                               + ", ".join(incomplete))
        return None

    def download_asset(self, asset: dict, destination: Path) -> Path:
        # API 附件 URL 同时支持公有/私有仓库；requests 在跨域重定向时移除认证头。
        url = asset.get("url") or asset["browser_download_url"]
        return download_file(url, destination, headers=self.headers("application/octet-stream"), timeout=300)

    def delete_artifact(self, artifact_id: int) -> None:
        with requests.delete(f"{self.base}/actions/artifacts/{int(artifact_id)}",
                             headers=self.headers(), timeout=30) as response:
            response.raise_for_status()

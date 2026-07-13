#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVE Online 客户端资源统一下载客户端
封装 build 查询、installer/resfileindex 索引与 CDN 文件缓存
"""

import os
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from evesde.utils.async_http import download_files
from evesde.utils.http_client import RetryableHTTPClient, create_session

TQ_JSON_URL = "https://binaries.eveonline.com/eveclient_TQ.json"
BINARIES_BASE = "https://binaries.eveonline.com"
RESOURCES_BASE = "https://resources.eveonline.com"

_client_instance: Optional["EveClient"] = None


class EveClientError(Exception):
    pass


class IndexEntry:
    def __init__(self, path: str, hash_value: str, size: int):
        self.path = path
        self.hash = hash_value
        self.size = size


class SharedCache:
    def client_version(self) -> str:
        raise NotImplementedError

    def iter_resources(self) -> Iterator[str]:
        raise NotImplementedError

    def has_resource(self, resource: str) -> bool:
        raise NotImplementedError

    def fetch(self, resource: str) -> bytes:
        raise NotImplementedError

    def path_of(self, resource: str) -> Path:
        raise NotImplementedError

    def hash_of(self, resource: str) -> str:
        raise NotImplementedError


def get_eve_client(cache_dir: Optional[Path] = None, **kwargs) -> "EveClient":
    global _client_instance
    if _client_instance is None:
        if cache_dir is None:
            raise EveClientError("尚未初始化 EveClient，请先调用 EveClient.from_tq() 或 set_eve_client()")
        _client_instance = EveClient(cache_dir, **kwargs)
    return _client_instance


def set_eve_client(client: "EveClient") -> None:
    global _client_instance
    _client_instance = client


class EveClient(SharedCache):
    """EVE 客户端 CDN 资源客户端，带磁盘缓存"""

    def __init__(
        self,
        cache_dir: Path,
        user_agent: str = "EveSDE/3.0",
        use_macos_build: bool = False,
        session: Optional[RetryableHTTPClient] = None,
        download_concurrency: int = 32,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.download_concurrency = download_concurrency

        if (self.cache_dir / "updater.exe").exists() or (self.cache_dir / "tq").exists():
            raise EveClientError("不能将游戏安装目录作为缓存目录")

        self.session = session or create_session(default_timeout=120, verify=False)
        self.session.session.headers.setdefault("User-Agent", user_agent)

        self.app_index: Dict[str, IndexEntry] = {}
        self.res_index: Dict[str, IndexEntry] = {}
        self._client_version = self._load_indexes(use_macos_build)

    @classmethod
    def from_tq(cls, cache_dir: Path, **kwargs) -> "EveClient":
        return cls(cache_dir, **kwargs)

    @staticmethod
    def _norm(resource: str) -> str:
        return resource.lower().replace("\\", "/")

    @staticmethod
    def _parse_build(client_data: dict) -> int:
        for key in ("build_number", "buildNumber", "build"):
            value = client_data.get(key)
            if value:
                return int(value)
        return 0

    def _load_index_text(self, content: str, index_dict: Dict[str, IndexEntry]) -> None:
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            resource_key = parts[0].strip().lower().replace("\\", "/")
            index_dict[resource_key] = IndexEntry(
                parts[1].strip(),
                parts[2].strip(),
                int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 0,
            )

    def _resolve_url(self, resource: str) -> Tuple[Path, str]:
        key = self._norm(resource)
        if key in self.app_index:
            entry = self.app_index[key]
            return self.cache_dir / entry.path, f"{BINARIES_BASE}/{entry.path}"
        if key in self.res_index:
            entry = self.res_index[key]
            return self.cache_dir / entry.path, f"{RESOURCES_BASE}/{entry.path}"
        raise EveClientError(f"资源未找到: {resource}")

    def _download_to_cache(self, dest: Path, url: str) -> bytes:
        if dest.exists():
            return dest.read_bytes()
        download_files(
            [(dest, url)],
            concurrency=1,
            user_agent=self.user_agent,
        )
        if not dest.exists():
            raise EveClientError(f"下载失败: {dest.name}")
        return dest.read_bytes()

    def ensure_files(
        self,
        items: List[Tuple[Path, str]],
        concurrency: Optional[int] = None,
        label: str = "",
    ) -> Tuple[int, int]:
        return download_files(
            items,
            concurrency=concurrency or self.download_concurrency,
            user_agent=self.user_agent,
            label=label,
        )

    def ensure_resources(
        self,
        resources: List[str],
        concurrency: Optional[int] = None,
        label: str = "",
    ) -> Tuple[int, int]:
        items = []
        for resource in resources:
            try:
                items.append(self._resolve_url(resource))
            except EveClientError:
                pass
        return self.ensure_files(items, concurrency=concurrency, label=label)

    def _load_indexes(self, use_macos_build: bool) -> int:
        response = self.session.get(TQ_JSON_URL, timeout=30)
        client_data = response.json()
        if client_data.get("protected"):
            raise EveClientError("游戏服务器处于保护状态")

        build = self._parse_build(client_data)
        if not build:
            raise EveClientError("无法从 eveclient_TQ.json 解析 build 号")

        index_filename = f"eveonline_{build}.txt"
        if use_macos_build:
            index_url = f"{BINARIES_BASE}/eveonlinemacOS_{build}.txt"
        else:
            index_url = f"{BINARIES_BASE}/eveonline_{build}.txt"

        index_content = self._download_to_cache(self.cache_dir / index_filename, index_url)
        self._load_index_text(index_content.decode("utf-8"), self.app_index)

        res_index_content = self.fetch("app:/resfileindex.txt")
        self._load_index_text(res_index_content.decode("utf-8"), self.res_index)
        print(f"[+] 客户端资源索引就绪 (build {build}, {len(self.res_index)} 条)")
        return build

    def client_version(self) -> str:
        return str(self._client_version)

    @property
    def build(self) -> int:
        return self._client_version

    def lookup(self, resource: str) -> Optional[IndexEntry]:
        key = self._norm(resource)
        return self.res_index.get(key) or self.app_index.get(key)

    def grep(self, pattern: str) -> List[Tuple[str, IndexEntry]]:
        rx = re.compile(pattern, re.IGNORECASE)
        return [(path, entry) for path, entry in self.res_index.items() if rx.search(path)]

    def has_resource(self, resource: str) -> bool:
        key = self._norm(resource)
        return key in self.app_index or key in self.res_index

    def iter_resources(self) -> Iterator[str]:
        yield from self.app_index.keys()
        yield from self.res_index.keys()

    def fetch(self, resource: str) -> bytes:
        dest, url = self._resolve_url(resource)
        return self._download_to_cache(dest, url)

    def fetch_cdn_path(self, cdn_path: str, binaries: bool = False) -> bytes:
        base = BINARIES_BASE if binaries else RESOURCES_BASE
        url = f"{base}/{cdn_path}"
        return self._download_to_cache(self.cache_dir / cdn_path, url)

    def path_of(self, resource: str) -> Path:
        dest, url = self._resolve_url(resource)
        self._download_to_cache(dest, url)
        return dest

    def hash_of(self, resource: str) -> str:
        entry = self.lookup(resource)
        if not entry:
            raise EveClientError(f"资源未找到: {resource}")
        return entry.hash

    def resfile_index_text(self) -> str:
        return self.fetch("app:/resfileindex.txt").decode("utf-8")

    def purge(self, keep_files: list[str]) -> None:
        valid_paths = {entry.path for entry in self.app_index.values()}
        valid_paths.update(entry.path for entry in self.res_index.values())
        valid_paths.update(keep_files)

        for root, _, files in os.walk(self.cache_dir):
            for file in files:
                file_path = Path(root) / file
                relative_path = str(file_path.relative_to(self.cache_dir))
                if relative_path not in valid_paths:
                    try:
                        file_path.unlink()
                    except OSError:
                        pass


CacheDownloader = EveClient
CacheError = EveClientError

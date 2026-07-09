"""
游戏资源缓存下载模块
提供对EVE Online游戏文件CDN的访问，创建本地磁盘缓存
"""

import os
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.http_client import create_session
from typing import Dict, Optional, Iterator
from urllib.parse import urljoin


class CacheError(Exception):
    """缓存相关错误"""
    pass


class IndexEntry:
    """索引条目"""
    def __init__(self, path: str, hash_value: str, size: int):
        self.path = path
        self.hash = hash_value
        self.size = size


class SharedCache:
    """共享缓存接口"""
    
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


class CacheDownloader(SharedCache):
    """提供对游戏文件CDN的访问，创建本地磁盘缓存"""
    
    def __init__(self, cache_dir: Path, user_agent: str, use_macos_build: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查是否误指向游戏安装目录
        if (self.cache_dir / "updater.exe").exists() or (self.cache_dir / "tq").exists():
            raise CacheError("不能将游戏安装目录作为缓存目录")
        
        self.session = create_session()
        self.session.session.headers.update({'User-Agent': user_agent})
        
        # 获取客户端版本
        response = self.session.get("https://binaries.eveonline.com/eveclient_TQ.json")
        client_data = response.json()
        
        if client_data.get('protected'):
            raise CacheError("游戏服务器处于保护状态")
        
        self._client_version = client_data.get('build_number', client_data.get('buildNumber', 0))
        self.app_index: Dict[str, IndexEntry] = {}
        self.res_index: Dict[str, IndexEntry] = {}
        
        # 下载并解析索引文件
        index_filename = f"eveonline_{self._client_version}.txt"
        if use_macos_build:
            index_url = f"https://binaries.eveonline.com/eveonlinemacOS_{self._client_version}.txt"
        else:
            index_url = f"https://binaries.eveonline.com/eveonline_{self._client_version}.txt"
        
        index_content = self._fetch_file(self.cache_dir / index_filename, index_url)
        self._load_index(index_content.decode('utf-8'), self.app_index)
        
        # 加载资源索引
        res_index_content = self.fetch("app:/resfileindex.txt")
        self._load_index(res_index_content.decode('utf-8'), self.res_index)
    
    def _load_index(self, content: str, index_dict: Dict[str, IndexEntry]):
        """解析索引文件"""
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 3:
                resource_path = parts[0].strip()
                file_path = parts[1].strip()
                hash_value = parts[2].strip()
                size = int(parts[3].strip()) if len(parts) > 3 else 0
                
                # 规范化资源路径
                resource_key = resource_path.lower().replace('\\', '/')
                index_dict[resource_key] = IndexEntry(file_path, hash_value, size)
    
    def _ensure_cached(self, file_path: Path, url: str) -> Optional[bytes]:
        """确保文件已缓存，如果不存在则下载"""
        if file_path.exists():
            return None
        
        response = self.session.get(url)
        data = response.content
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        
        return data
    
    def _fetch_file(self, file_path: Path, url: str) -> bytes:
        """获取文件，优先使用缓存"""
        cached_data = self._ensure_cached(file_path, url)
        if cached_data is not None:
            return cached_data
        return file_path.read_bytes()
    
    def client_version(self) -> str:
        return self._client_version
    
    def iter_resources(self) -> Iterator[str]:
        """迭代所有资源路径"""
        yield from self.app_index.keys()
        yield from self.res_index.keys()
    
    def has_resource(self, resource: str) -> bool:
        """检查资源是否存在"""
        resource = resource.lower().replace('\\', '/')
        return resource in self.app_index or resource in self.res_index
    
    def fetch(self, resource: str) -> bytes:
        """获取资源内容"""
        resource = resource.lower().replace('\\', '/')
        
        if resource in self.app_index:
            entry = self.app_index[resource]
            url = f"https://binaries.eveonline.com/{entry.path}"
            return self._fetch_file(self.cache_dir / entry.path, url)
        elif resource in self.res_index:
            entry = self.res_index[resource]
            url = f"https://resources.eveonline.com/{entry.path}"
            return self._fetch_file(self.cache_dir / entry.path, url)
        else:
            raise CacheError(f"资源未找到: {resource}")
    
    def path_of(self, resource: str) -> Path:
        """获取资源的本地路径，如果不存在则下载"""
        resource = resource.lower().replace('\\', '/')
        
        if resource in self.app_index:
            entry = self.app_index[resource]
            file_path = self.cache_dir / entry.path
            url = f"https://binaries.eveonline.com/{entry.path}"
            self._ensure_cached(file_path, url)
            return file_path
        elif resource in self.res_index:
            entry = self.res_index[resource]
            file_path = self.cache_dir / entry.path
            url = f"https://resources.eveonline.com/{entry.path}"
            self._ensure_cached(file_path, url)
            return file_path
        else:
            raise CacheError(f"资源未找到: {resource}")
    
    def hash_of(self, resource: str) -> str:
        """获取资源的哈希值"""
        resource = resource.lower().replace('\\', '/')
        
        if resource in self.app_index:
            return self.app_index[resource].hash
        elif resource in self.res_index:
            return self.res_index[resource].hash
        else:
            raise CacheError(f"资源未找到: {resource}")
    
    def purge(self, keep_files: list[str]):
        """删除不在当前索引中的本地文件"""
        valid_paths = set()
        for entry in self.app_index.values():
            valid_paths.add(entry.path)
        for entry in self.res_index.values():
            valid_paths.add(entry.path)
        
        # 添加保留文件
        for keep_file in keep_files:
            valid_paths.add(keep_file)
        
        # 遍历缓存目录，删除无效文件
        for root, dirs, files in os.walk(self.cache_dir):
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.cache_dir)
                if str(relative_path) not in valid_paths:
                    try:
                        file_path.unlink()
                    except Exception:
                        pass

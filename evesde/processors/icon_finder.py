#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标查找器模块
用于查找EVE Online客户端中的图标文件
支持从在线服务器获取图标和resfile数据
"""

from evesde.paths import PROJECT_ROOT
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from evesde.utils.eve_client import EveClient, get_eve_client
import evesde.processors.jsonl_loader as jsonl_loader


class IconFinder:
    """EVE图标查找器"""
    
    def __init__(self, config: Dict = None):
        """初始化图标查找器"""
        self.config = config or {}
        self.project_root = PROJECT_ROOT
        
        self.icon_id_to_path_map = {}
        self.resfile_index_map = {}
        self.local_cache_map = {}
        self.cache_file = self.project_root / "icon_cache.json"
        
        self.eve_client: EveClient = self.config.get("eve_client") or get_eve_client(
            self.project_root / self.config.get("paths", {}).get("client_cache", "cache/client")
        )
        
        self._load_icon_mappings()
        self._load_resfile_index()
        self._load_local_cache()
    
    def _load_icon_mappings(self):
        """加载icons.jsonl，建立iconID到文件路径的映射"""
        print("[+] 加载图标映射数据...")
        
        sde_input = self.config.get("paths", {}).get("sde_input", "cache/sde_jsonl")
        icons_file = self.project_root / sde_input / "icons.jsonl"
        if not icons_file.exists():
            print(f"[x] 图标文件不存在: {icons_file}")
            return
        
        try:
            icons_list = jsonl_loader.load_jsonl(str(icons_file))
            
            for icon_data in icons_list:
                icon_id = icon_data.get('_key')
                icon_file = icon_data.get('iconFile', '')
                
                if icon_id and icon_file:
                    # 将路径转换为小写以便匹配
                    self.icon_id_to_path_map[icon_id] = icon_file.lower()
            
            print(f"[+] 加载了 {len(self.icon_id_to_path_map)} 个图标映射")
            
        except Exception as e:
            print(f"[x] 加载图标映射时出错: {e}")
    
    def _load_resfile_index(self):
        for res_path, entry in self.eve_client.res_index.items():
            self.resfile_index_map[res_path] = (entry.path, entry.hash, str(entry.size))
    
    def _load_local_cache(self):
        """加载本地缓存哈希表"""
        if not self.cache_file.exists():
            print("[+] 本地缓存文件不存在，将创建新的缓存")
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                self.local_cache_map = cache_data.get('cache_map', {})
                print(f"[+] 加载本地缓存: {len(self.local_cache_map)} 个文件")
        except Exception as e:
            print(f"[!] 加载本地缓存失败: {e}")
            self.local_cache_map = {}
    
    def _save_local_cache(self):
        """保存本地缓存哈希表"""
        try:
            cache_data = {
                'cache_map': self.local_cache_map,
                'version': '1.0',
                'description': 'EVE图标本地缓存哈希表'
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"[+] 保存本地缓存: {len(self.local_cache_map)} 个文件")
        except Exception as e:
            print(f"[!] 保存本地缓存失败: {e}")
    
    def _add_to_cache(self, md5_hash: str, filename: str, file_path: str):
        """添加文件到本地缓存"""
        self.local_cache_map[md5_hash.lower()] = (filename, file_path)
    
    def _get_from_cache(self, md5_hash: str) -> Optional[Tuple[str, str]]:
        """从本地缓存获取文件信息"""
        return self.local_cache_map.get(md5_hash.lower())
    
    def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """计算文件的MD5哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"[!] 计算文件哈希失败 {file_path}: {e}")
            return None
    
    def _check_local_file_integrity(self, resource_path: str, local_file_path: str) -> bool:
        """
        检查本地文件的完整性
        
        Args:
            resource_path: 资源路径
            local_file_path: 本地文件路径
            
        Returns:
            bool: 文件是否完整且未损坏
        """
        if resource_path not in self.resfile_index_map:
            return False
        
        file_path, expected_hash, expected_size = self.resfile_index_map[resource_path]
        
        # 如果没有哈希值，只检查文件是否存在
        if not expected_hash:
            return os.path.exists(local_file_path)
        
        # 检查文件是否存在
        if not os.path.exists(local_file_path):
            return False
        
        # 检查文件大小（如果提供了）
        if expected_size and expected_size != "0":
            try:
                actual_size = os.path.getsize(local_file_path)
                if actual_size != int(expected_size):
                    print(f"[!] 文件大小不匹配: {local_file_path} (期望: {expected_size}, 实际: {actual_size})")
                    return False
            except Exception as e:
                print(f"[!] 检查文件大小失败: {e}")
                return False
        
        # 检查文件哈希值
        try:
            actual_hash = self._calculate_file_hash(Path(local_file_path))
            if actual_hash and actual_hash.lower() == expected_hash.lower():
                return True
            else:
                print(f"[!] 文件哈希不匹配: {local_file_path} (期望: {expected_hash}, 实际: {actual_hash})")
                return False
        except Exception as e:
            print(f"[!] 计算文件哈希失败: {e}")
            return False
    
    def prefetch_resources(self, resource_paths: List[str], label: str = "资源") -> None:
        unique = list(dict.fromkeys(resource_paths))
        self.eve_client.ensure_resources(unique, label=label)

    def prefetch_icon_ids(self, icon_ids: list, label: str = "图标") -> None:
        paths = [
            self.icon_id_to_path_map[icon_id]
            for icon_id in icon_ids
            if icon_id in self.icon_id_to_path_map
        ]
        self.prefetch_resources(paths, label=label)

    def _get_icon_file_content(self, resource_path: str) -> Optional[bytes]:
        if resource_path not in self.resfile_index_map:
            return None
        try:
            return self.eve_client.fetch(resource_path)
        except Exception:
            return None
    
    def get_icon_file_content(self, icon_id: int) -> Optional[bytes]:
        """
        根据iconID获取图标文件内容
        优先检查本地缓存，然后检查本地客户端文件，最后从在线服务器获取
        
        Args:
            icon_id: 图标ID
            
        Returns:
            图标文件的二进制内容，如果未找到则返回None
        """
        if not icon_id or icon_id not in self.icon_id_to_path_map:
            return None
        
        # 获取资源路径
        resource_path = self.icon_id_to_path_map[icon_id]
        
        # 首先检查本地缓存
        if resource_path in self.resfile_index_map:
            _, expected_hash, _ = self.resfile_index_map[resource_path]
            if expected_hash:
                cached_info = self._get_from_cache(expected_hash)
                if cached_info:
                    cached_filename, cached_path = cached_info
                    if os.path.exists(cached_path):
                        try:
                            return Path(cached_path).read_bytes()
                        except Exception:
                            del self.local_cache_map[expected_hash.lower()]

        if resource_path in self.resfile_index_map:
            remote_file_path, expected_hash, _ = self.resfile_index_map[resource_path]
            cached_path = self.eve_client.cache_dir / remote_file_path
            if cached_path.exists() and self._check_local_file_integrity(resource_path, str(cached_path)):
                try:
                    content = cached_path.read_bytes()
                    if expected_hash:
                        self._add_to_cache(expected_hash, f"icon_{icon_id}.png", str(cached_path))
                    return content
                except Exception:
                    pass

        online_content = self._get_icon_file_content(resource_path)
        if online_content:
            if resource_path in self.resfile_index_map:
                _, expected_hash, _ = self.resfile_index_map[resource_path]
                if expected_hash:
                    filename = f"icon_{icon_id}.png"
                    # 这里可以保存到临时文件或自定义目录
                    # 暂时不保存，只记录到缓存中
                    self._add_to_cache(expected_hash, filename, f"online:{icon_id}")
            
            return online_content
        
        return None
    
    def find_icon_file_path(self, icon_id: int) -> Optional[str]:
        """根据 iconID 查找已缓存的图标文件路径"""
        if not icon_id or icon_id not in self.icon_id_to_path_map:
            return None
        resource_path = self.icon_id_to_path_map[icon_id]
        if resource_path not in self.resfile_index_map:
            return None
        remote_file_path, _, _ = self.resfile_index_map[resource_path]
        cached_path = self.eve_client.cache_dir / remote_file_path
        return str(cached_path) if cached_path.exists() else None
    
    def get_icon_info(self, icon_id: int) -> Dict[str, Optional[str]]:
        """
        获取图标的详细信息
        
        Args:
            icon_id: 图标ID
            
        Returns:
            包含图标信息的字典
        """
        result = {
            "icon_id": icon_id,
            "resource_path": None,
            "local_path": None,
            "online_available": False,
            "exists": False
        }
        
        if icon_id in self.icon_id_to_path_map:
            result["resource_path"] = self.icon_id_to_path_map[icon_id]
            
            # 检查是否可以从在线获取
            content = self.get_icon_file_content(icon_id)
            if content:
                result["online_available"] = True
                result["exists"] = True
            
            # 检查本地文件
            local_path = self.find_icon_file_path(icon_id)
            if local_path:
                result["local_path"] = local_path
                result["exists"] = True
        
        return result
    
    def batch_find_icons(self, icon_ids: list) -> Dict[int, Dict[str, Optional[str]]]:
        """
        批量查找图标信息
        
        Args:
            icon_ids: 图标ID列表
            
        Returns:
            iconID -> 图标信息的字典
        """
        results = {}
        
        for icon_id in icon_ids:
            results[icon_id] = self.get_icon_info(icon_id)
        
        return results
    
    def get_cached_icon_filename(self, icon_id: int) -> Optional[str]:
        """
        获取缓存的图标文件名，避免重复复制
        
        Args:
            icon_id: 图标ID
            
        Returns:
            缓存的图标文件名，如果没有缓存则返回None
        """
        if icon_id not in self.icon_id_to_path_map:
            return None
        
        resource_path = self.icon_id_to_path_map[icon_id]
        if resource_path not in self.resfile_index_map:
            return None
        
        _, expected_hash, _ = self.resfile_index_map[resource_path]
        if not expected_hash:
            return None
        
        cached_info = self._get_from_cache(expected_hash)
        if cached_info:
            cached_filename, cached_path = cached_info
            if os.path.exists(cached_path) and not cached_path.startswith("online:"):
                return cached_filename
        
        return None
    
    def copy_icon_to_custom_dir(self, icon_id: int, target_filename: str, 
                               custom_dir: str = "cache/custom_icons") -> bool:
        """
        将图标文件复制到自定义目录
        优先使用缓存文件，避免重复下载和复制
        
        Args:
            icon_id: 图标ID
            target_filename: 目标文件名
            custom_dir: 自定义目录名
            
        Returns:
            是否成功复制
        """
        # 确保目标目录存在
        target_dir = self.project_root / custom_dir
        target_dir.mkdir(exist_ok=True)
        target_path = target_dir / target_filename
        
        # 如果目标文件已存在，直接返回成功
        if target_path.exists():
            # print(f"[+] 目标文件已存在，跳过复制: {target_filename}")
            return True
        
        # 检查是否可以从缓存获取
        if icon_id in self.icon_id_to_path_map:
            resource_path = self.icon_id_to_path_map[icon_id]
            if resource_path in self.resfile_index_map:
                _, expected_hash, _ = self.resfile_index_map[resource_path]
                if expected_hash:
                    cached_info = self._get_from_cache(expected_hash)
                    if cached_info:
                        cached_filename, cached_path = cached_info
                        if os.path.exists(cached_path) and not cached_path.startswith("online:"):
                            try:
                                import shutil
                                shutil.copy2(cached_path, target_path)
                                return True
                            except Exception:
                                pass
        
        # 获取图标内容（在线或本地）
        content = self.get_icon_file_content(icon_id)
        if not content:
            return False

        try:
            with open(target_path, 'wb') as f:
                f.write(content)
            
            # 将新保存的文件添加到缓存
            if icon_id in self.icon_id_to_path_map:
                resource_path = self.icon_id_to_path_map[icon_id]
                if resource_path in self.resfile_index_map:
                    _, expected_hash, _ = self.resfile_index_map[resource_path]
                    if expected_hash:
                        self._add_to_cache(expected_hash, target_filename, str(target_path))
            
            return True
        except Exception as e:
            print(f"[x] 保存图标失败 {icon_id}: {e}")
            return False
    
    def get_icon_batch(self, icon_ids: list) -> Dict[int, bool]:
        self.prefetch_icon_ids(icon_ids)
        results = {}
        for icon_id in icon_ids:
            results[icon_id] = self.get_icon_file_content(icon_id) is not None
        ok = sum(results.values())
        print(f"[+] 图标批量获取: {ok}/{len(icon_ids)}")
        return results
    
    def generate_groups_icon_mapping(self, groups_data: Dict) -> Dict[int, str]:
        """
        为groups数据生成图标映射
        
        Args:
            groups_data: 组数据字典
            
        Returns:
            group_id -> icon_filename的映射
        """
        icon_ids = [
            group_info.get('iconID', 0)
            for group_info in groups_data.values()
            if group_info.get('iconID', 0)
        ]
        self.prefetch_icon_ids(icon_ids, label="组图标")

        icon_mapping = {}
        found_count = 0
        missing_count = 0
        
        for group_id, group_info in groups_data.items():
            icon_id = group_info.get('iconID', 0)
            
            if icon_id:
                # 尝试获取图标内容并保存
                target_filename = f"group_{group_id}.png"
                if self.copy_icon_to_custom_dir(icon_id, target_filename):
                    icon_mapping[group_id] = target_filename
                    found_count += 1
                else:
                    icon_mapping[group_id] = "category_default.png"
                    missing_count += 1
            else:
                icon_mapping[group_id] = "category_default.png"
                missing_count += 1
        
        print(f"[+] Groups图标映射完成:")
        print(f"    - 找到并复制: {found_count} 个")
        print(f"    - 使用默认图标: {missing_count} 个")
        
        return icon_mapping
    
    def save_cache(self):
        """保存缓存到文件"""
        self._save_local_cache()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            'total_cached': len(self.local_cache_map),
            'local_files': len([info for info in self.local_cache_map.values() 
                               if os.path.exists(info[1]) and not info[1].startswith("online:")]),
            'online_cached': len([info for info in self.local_cache_map.values() 
                                 if info[1].startswith("online:")])
        }


def main():
    """测试函数"""
    print("[+] 图标查找器测试（在线模式）")
    
    finder = IconFinder()
    
    # 测试一些图标ID
    test_icon_ids = [21, 15, 73, 1002, 2403]
    
    print("\n[+] 测试图标查找:")
    for icon_id in test_icon_ids:
        info = finder.get_icon_info(icon_id)
        print(f"Icon {icon_id}: {info}")
    
    print("\n[+] 测试批量获取:")
    batch_results = finder.get_icon_batch(test_icon_ids[:3])
    for icon_id, success in batch_results.items():
        status = "成功" if success else "失败"
        print(f"图标 {icon_id}: {status}")
    
    print("\n[+] 图标查找器测试完成")


if __name__ == "__main__":
    main()

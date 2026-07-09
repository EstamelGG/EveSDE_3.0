#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标查找器模块
用于查找EVE Online客户端中的图标文件
支持从在线服务器获取图标和resfile数据
"""

import json
import os
import platform
import tempfile
import shutil
import hashlib
from pathlib import Path
from utils.http_client import create_session
from typing import Dict, Optional, Tuple
import scripts.jsonl_loader as jsonl_loader


class IconFinder:
    """EVE图标查找器"""
    
    def __init__(self, config: Dict = None):
        """初始化图标查找器"""
        self.config = config or {}
        self.project_root = Path(__file__).parent.parent
        
        # 缓存数据
        self.icon_id_to_path_map = {}  # iconID -> iconFile路径
        self.resfile_index_map = {}    # 资源路径 -> (本地文件路径, 哈希值, 文件大小)
        
        # 本地缓存哈希表：MD5 -> (文件名, 文件路径)
        self.local_cache_map = {}      # MD5哈希值 -> (文件名, 完整路径)
        self.cache_file = self.project_root / "icon_cache.json"
        
        # 在线服务器配置
        self.session = create_session(verify=False)  # 禁用SSL验证
        self.build_info = None
        
        # 平台相关路径（保留作为备用）
        self.eve_client_paths = self._get_eve_client_paths()
        
        # 加载数据
        self._load_icon_mappings()
        self._load_resfile_index()
        self._load_local_cache()
    
    def _get_eve_client_paths(self) -> Dict[str, Optional[str]]:
        """获取EVE客户端路径（根据操作系统）"""
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            base_path = Path.home() / "Library/Application Support/EVE Online/SharedCache/"
            return {
                "resfileindex": str(base_path / "tq/EVE.app/Contents/Resources/build/resfileindex.txt"),
                "resfiles": str(base_path / "ResFiles")
            }
        elif system == "windows":
            # Windows路径暂时留空，后续实现
            return {
                "resfileindex": None,
                "resfiles": None
            }
        else:
            return {
                "resfileindex": None, 
                "resfiles": None
            }
    
    def _load_icon_mappings(self):
        """加载icons.jsonl，建立iconID到文件路径的映射"""
        print("[+] 加载图标映射数据...")
        
        icons_file = self.project_root / "sde_jsonl/icons.jsonl"
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
    
    def _get_build_info(self) -> Optional[Dict]:
        """获取EVE客户端的最新构建信息"""
        if self.build_info:
            return self.build_info
        
        try:
            print("[+] 获取EVE客户端构建信息...")
            response = self.session.get("https://binaries.eveonline.com/eveclient_TQ.json")
            self.build_info = response.json()
            print(f"[+] 当前构建版本: {self.build_info.get('build')}")
            return self.build_info
        except Exception as e:
            print(f"[x] 获取构建信息失败: {e}")
            return None
    
    def _get_resfile_index_content(self) -> Optional[str]:
        """从在线服务器获取resfileindex.txt内容"""
        build_info = self._get_build_info()
        if not build_info:
            return None
        
        build_number = build_info.get('build')
        if not build_number:
            return None
        
        try:
            print("[+] 从在线服务器获取resfileindex...")
            installer_url = f"https://binaries.eveonline.com/eveonline_{build_number}.txt"
            response = self.session.get(installer_url)
            
            # 解析installer文件找到resfileindex
            resfileindex_path = None
            for line in response.text.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split(',')
                if len(parts) >= 2 and parts[0] == "app:/resfileindex.txt":
                    resfileindex_path = parts[1]
                    break
            
            if not resfileindex_path:
                print("[x] 在installer文件中未找到resfileindex路径")
                return None
            
            # 下载resfileindex文件内容
            resfile_url = f"https://binaries.eveonline.com/{resfileindex_path}"
            response = self.session.get(resfile_url)
            
            print("[+] resfileindex获取完成")
            return response.text
            
        except Exception as e:
            print(f"[x] 获取resfileindex失败: {e}")
            return None
    
    def _load_resfile_index(self):
        """加载EVE客户端的resfileindex.txt文件"""
        # 首先尝试从在线服务器获取
        resfile_content = self._get_resfile_index_content()
        
        # 如果在线获取失败，尝试本地客户端路径
        if not resfile_content:
            resfileindex_path = self.eve_client_paths.get("resfileindex")
            
            if not resfileindex_path or not os.path.exists(resfileindex_path):
                print("[-] 无法获取resfileindex文件（在线和本地都失败）")
                return
            
            try:
                with open(resfileindex_path, 'r', encoding='utf-8') as f:
                    resfile_content = f.read()
            except Exception as e:
                print(f"[x] 读取本地resfileindex失败: {e}")
                return
        
        print("[+] 解析资源索引...")
        
        try:
            for line_num, line in enumerate(resfile_content.split('\n'), 1):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',')
                if len(parts) >= 3:
                    resource_path = parts[0].lower()  # 资源路径，转小写
                    file_path = parts[1]              # 本地文件路径
                    file_hash = parts[2]              # 文件哈希值
                    file_size = parts[3] if len(parts) > 3 else "0"  # 文件大小
                    self.resfile_index_map[resource_path] = (file_path, file_hash, file_size)
                elif len(parts) >= 2:
                    # 兼容旧格式（没有哈希值）
                    resource_path = parts[0].lower()
                    file_path = parts[1]
                    self.resfile_index_map[resource_path] = (file_path, "", "0")
                else:
                    if line_num <= 10:  # 只显示前10行的警告
                        print(f"[!] 第{line_num}行格式不正确: {line}")
            
            print(f"[+] 加载了 {len(self.resfile_index_map)} 个资源映射")
            
        except Exception as e:
            print(f"[x] 解析资源索引时出错: {e}")
    
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
    
    def _get_icon_file_content(self, resource_path: str) -> Optional[bytes]:
        """从在线服务器获取图标文件内容"""
        if resource_path not in self.resfile_index_map:
            return None
        
        remote_file_path, _, _ = self.resfile_index_map[resource_path]
        
        try:
            # 从EVE资源服务器获取
            download_url = f"https://resources.eveonline.com/{remote_file_path}"
            print(f"[+] 获取图标: {download_url}")
            
            response = self.session.get(download_url)
            
            print(f"[+] 图标获取完成: {resource_path}")
            return response.content
            
        except Exception as e:
            print(f"[x] 获取图标失败 {resource_path}: {e}")
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
                            with open(cached_path, 'rb') as f:
                                print(f"[+] 使用缓存图标文件: {icon_id} -> {cached_filename}")
                                return f.read()
                        except Exception as e:
                            print(f"[!] 读取缓存图标文件失败 {cached_path}: {e}")
                    else:
                        print(f"[!] 缓存文件不存在，从缓存中移除: {cached_path}")
                        # 从缓存中移除不存在的文件
                        del self.local_cache_map[expected_hash.lower()]
        
        # 其次检查本地客户端文件（如果可用）
        if resource_path in self.resfile_index_map:
            remote_file_path, expected_hash, _ = self.resfile_index_map[resource_path]
            resfiles_dir = self.eve_client_paths.get("resfiles")
            
            if resfiles_dir:
                local_full_path = os.path.join(resfiles_dir, remote_file_path)
                
                # 检查本地文件完整性
                if self._check_local_file_integrity(resource_path, local_full_path):
                    try:
                        with open(local_full_path, 'rb') as f:
                            content = f.read()
                            print(f"[+] 使用本地客户端图标文件: {icon_id}")
                            
                            # 将文件添加到缓存
                            if expected_hash:
                                filename = f"icon_{icon_id}.png"
                                self._add_to_cache(expected_hash, filename, local_full_path)
                            
                            return content
                    except Exception as e:
                        print(f"[!] 读取本地图标文件失败 {local_full_path}: {e}")
                else:
                    print(f"[!] 本地图标文件损坏或不完整: {local_full_path}")
        
        # 最后从在线服务器获取
        online_content = self._get_icon_file_content(resource_path)
        if online_content:
            print(f"[+] 从在线获取图标: {icon_id}")
            
            # 将下载的内容添加到缓存
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
        """
        根据iconID查找本地图标文件路径（仅用于本地客户端文件）
        
        Args:
            icon_id: 图标ID
            
        Returns:
            本地图标文件的完整路径，如果未找到则返回None
        """
        if not icon_id or icon_id not in self.icon_id_to_path_map:
            return None
        
        # 获取资源路径
        resource_path = self.icon_id_to_path_map[icon_id]
        
        # 仅检查本地客户端文件
        if resource_path not in self.resfile_index_map:
            return None
        
        remote_file_path, _, _ = self.resfile_index_map[resource_path]
        resfiles_dir = self.eve_client_paths.get("resfiles")
        
        if resfiles_dir:
            full_path = os.path.join(resfiles_dir, remote_file_path)
            if os.path.exists(full_path):
                return full_path
        
        return None
    
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
                               custom_dir: str = "custom_icons") -> bool:
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
                                print(f"[+] 从缓存复制图标: {icon_id} -> {target_filename}")
                                return True
                            except Exception as e:
                                print(f"[!] 从缓存复制失败: {e}")
        
        # 获取图标内容（在线或本地）
        content = self.get_icon_file_content(icon_id)
        if not content:
            print(f"[-] 无法获取图标内容: {icon_id}")
            return False
        
        try:
            with open(target_path, 'wb') as f:
                f.write(content)
            print(f"[+] 保存图标: {icon_id} -> {target_filename}")
            
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
        """
        批量获取图标文件内容
        
        Args:
            icon_ids: 图标ID列表
            
        Returns:
            iconID -> 是否获取成功的字典
        """
        print(f"[+] 开始批量获取 {len(icon_ids)} 个图标...")
        
        results = {}
        success_count = 0
        
        for i, icon_id in enumerate(icon_ids, 1):
            print(f"[+] 处理图标 {i}/{len(icon_ids)}: {icon_id}")
            
            content = self.get_icon_file_content(icon_id)
            if content:
                results[icon_id] = True
                success_count += 1
            else:
                results[icon_id] = False
        
        print(f"[+] 批量获取完成: 成功 {success_count}/{len(icon_ids)} 个")
        return results
    
    def generate_groups_icon_mapping(self, groups_data: Dict) -> Dict[int, str]:
        """
        为groups数据生成图标映射
        
        Args:
            groups_data: 组数据字典
            
        Returns:
            group_id -> icon_filename的映射
        """
        print("[+] 生成groups图标映射...")
        
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EVE SDE 本地化数据提取器
"""

import os
import re
import pickle
import json
import shutil
import platform
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional, Tuple
from utils.http_client import create_session

class LocalizationExtractor:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.localization_dir = project_root / "localization"
        self.raw_dir = self.localization_dir / "raw"
        self.extra_dir = self.localization_dir / "extra"
        self.output_dir = self.localization_dir / "output"

        # 网络下载相关
        self.session = create_session(verify=False)  # 禁用SSL验证
        self.build_info = None
        self.resfile_index_map = {}
        
        # 创建必要的目录
        self._create_directories()
    
    def _create_directories(self):
        """创建必要的目录结构"""
        for directory in [self.raw_dir, self.extra_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[+] 创建目录: {directory}")
    
    def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """计算文件的MD5哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"[x] 计算文件哈希失败 {file_path}: {e}")
            return None
    
    
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
    
    def get_resfileindex_path(self) -> Optional[str]:
        """
        从在线服务器获取EVE Online的resfileindex.txt文件
        """
        # 从在线服务器获取
        resfile_content = self._get_resfile_index_content()
        if resfile_content:
            # 将在线内容保存到临时文件
            temp_file = self.raw_dir / "resfileindex.txt"
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(resfile_content)
                print(f"[+] 在线resfileindex已保存到: {temp_file}")
                return str(temp_file)
            except Exception as e:
                print(f"[x] 保存在线resfileindex失败: {e}")
                return None
        else:
            print("[x] 无法从在线服务器获取resfileindex")
            return None
    
    def _download_pickle_file(self, lang_code: str, file_path: str) -> Optional[bytes]:
        """从网络下载pickle文件内容"""
        try:
            # 从EVE资源服务器获取
            download_url = f"https://resources.eveonline.com/{file_path}"
            print(f"[+] 开始下载 {lang_code}...")
            print(f"[+] 下载URL: {download_url}")
            
            response = self.session.get(download_url, timeout=60)
            
            print(f"[+] {lang_code} 下载完成")
            return response.content
            
        except Exception as e:
            print(f"[x] 下载本地化文件失败 {lang_code}: {e}")
            return None
    
    def get_localization_pickles(self) -> Dict[str, str]:
        """
        从resfileindex.txt文件中搜索本地化pickle文件的信息
        仅从网络下载，不依赖本地客户端文件
        支持文件哈希验证
        """
        resfileindex_path = self.get_resfileindex_path()
        if not resfileindex_path:
            print("[x] 无法获取resfileindex.txt文件路径")
            return {}
        
        # 正则表达式模式，匹配localization_fsd_[\w-]+.pickle格式的文件，包含哈希值
        # resfileindex格式通常是: 文件路径,哈希值,大小,其他信息
        pattern = r'res:/localizationfsd/localization_fsd_([\w-]+)\.pickle,([^,]+),([^,]+)'
        
        result = {}
        
        try:
            with open(resfileindex_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            matches = re.findall(pattern, content)
            
            # 过滤掉"main"语言并标准化语言代码
            valid_matches = []
            for lang_code, file_path, file_hash in matches:
                if lang_code.lower() != "main":
                    if lang_code == "en-us":
                        lang_code = "en"
                    valid_matches.append((lang_code, file_path, file_hash))
            
            if not valid_matches:
                print("[!] 未找到有效的本地化pickle文件")
                return {}
            
            print(f"[+] 找到 {len(valid_matches)} 个本地化文件，检查下载状态和文件完整性...")
            
            # 统计变量
            downloaded_count = 0
            skipped_count = 0
            re_downloaded_count = 0
            
            # 检查并下载缺失的文件
            for lang_code, file_path, expected_hash in valid_matches:
                target_file = self.raw_dir / f"localization_fsd_{lang_code}.pickle"
                
                # 检查文件是否已存在且哈希值正确
                if target_file.exists():
                    # 计算现有文件的哈希值
                    current_hash = self._calculate_file_hash(target_file)
                    if current_hash and current_hash.lower() == expected_hash.lower():
                        print(f"[+] 文件已存在且哈希值正确，跳过下载: {target_file}")
                        result[lang_code] = str(target_file)
                        skipped_count += 1
                    else:
                        print(f"[!] 文件存在但哈希值不匹配，需要重新下载: {target_file}")
                        print(f"    期望哈希: {expected_hash}")
                        print(f"    实际哈希: {current_hash}")
                        # 删除旧文件并重新下载
                        target_file.unlink()
                        # 继续到下载逻辑
                        pickle_content = self._download_pickle_file(lang_code, file_path)
                        if pickle_content:
                            try:
                                with open(target_file, 'wb') as f:
                                    f.write(pickle_content)
                                result[lang_code] = str(target_file)
                                print(f"[+] 重新下载的pickle文件已保存: {target_file}")
                                re_downloaded_count += 1
                            except Exception as e:
                                print(f"[x] 保存重新下载的pickle文件失败: {e}")
                        else:
                            print(f"[!] 无法重新下载本地化pickle文件: {lang_code}")
                else:
                    # 从网络下载pickle文件
                    print(f"[+] 文件不存在，开始下载: {lang_code}")
                    pickle_content = self._download_pickle_file(lang_code, file_path)
                    if pickle_content:
                        # 保存到raw目录
                        try:
                            with open(target_file, 'wb') as f:
                                f.write(pickle_content)
                            result[lang_code] = str(target_file)
                            print(f"[+] 网络下载的pickle文件已保存: {target_file}")
                            downloaded_count += 1
                        except Exception as e:
                            print(f"[x] 保存网络下载的pickle文件失败: {e}")
                    else:
                        print(f"[!] 无法下载本地化pickle文件: {lang_code}")
            
            # 显示下载统计
            print(f"[+] 下载统计: 新下载 {downloaded_count} 个文件，重新下载 {re_downloaded_count} 个文件，跳过 {skipped_count} 个正确文件")
            
            return result
        
        except Exception as e:
            print(f"[x] 处理resfileindex.txt文件时出错: {e}")
            return {}
    
    def copy_localization_pickles_to_raw(self) -> Dict[str, str]:
        """
        从网络下载本地化pickle文件到项目的raw目录
        仅使用网络下载，不依赖本地客户端文件
        检查现有文件完整性，通过哈希验证确保文件正确性
        """
        # 创建raw目录（如果不存在）
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"[+] 确保raw目录存在: {self.raw_dir}")
        
        # 获取本地化pickle文件（仅网络下载）
        localization_pickles = self.get_localization_pickles()
        if not localization_pickles:
            print("[x] 未找到本地化pickle文件")
            return {}
        
        result = {}
        
        for lang_code, source_path in localization_pickles.items():
            # 所有文件都是从网络下载到raw目录的，直接使用
            result[lang_code] = source_path
            print(f"[+] 已下载本地化pickle文件: {source_path}")
        
        return result
    
    def unpickle_localization_files(self) -> Dict[str, Dict[str, Any]]:
        """
        解包raw目录中的本地化pickle文件到extra目录
        """
        if not self.raw_dir.exists():
            print(f"[x] raw目录不存在: {self.raw_dir}")
            return {}
        
        # 如果extra目录存在，则先删除
        if self.extra_dir.exists():
            shutil.rmtree(self.extra_dir)
            print(f"[+] 已删除现有的extra目录: {self.extra_dir}")
        
        # 创建extra目录
        self.extra_dir.mkdir(parents=True, exist_ok=True)
        print(f"[+] 已创建extra目录: {self.extra_dir}")
        
        result = {}
        
        # 获取raw目录中的所有pickle文件
        pickle_files = [f for f in self.raw_dir.iterdir() 
                       if f.name.startswith("localization_fsd_") and f.name.endswith(".pickle")]
        
        if not pickle_files:
            print(f"[x] 在{self.raw_dir}目录中没有找到本地化pickle文件")
            return {}
        
        for pickle_file in pickle_files:
            # 从文件名中提取语言代码
            lang_code = pickle_file.name.replace("localization_fsd_", "").replace(".pickle", "")
            
            try:
                # 解包pickle文件
                with open(pickle_file, 'rb') as f:
                    data = pickle.load(f)
                
                # 提取语言代码和本地化数据
                file_lang_code, translations = data
                
                # 将本地化数据转换为更易读的格式
                processed_data = {}
                for msg_id, msg_tuple in translations.items():
                    text, meta1, meta2 = msg_tuple
                    processed_data[str(msg_id)] = {
                        "text": text,
                        "metadata": {
                            "meta1": meta1,
                            "meta2": meta2
                        }
                    }
                
                # 为每种语言创建一个子目录
                lang_dir = self.extra_dir / lang_code
                lang_dir.mkdir(parents=True, exist_ok=True)
                
                # 保存为JSON格式
                json_file = lang_dir / f"{lang_code}_localization.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_data, f, ensure_ascii=False, indent=2)
                
                # 同时保存原始pickle格式
                pickle_output = lang_dir / f"{lang_code}_localization.pkl"
                with open(pickle_output, 'wb') as f:
                    pickle.dump(processed_data, f)
                
                print(f"[+] 已解包: {pickle_file.name} -> {lang_dir}")
                result[lang_code] = processed_data
                
            except Exception as e:
                print(f"[x] 解包文件时出错 {pickle_file.name}: {e}")
        
        return result
    
    def create_combined_localization(self, unpickled_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        """
        创建合并后的本地化数据结构
        """
        combined_data = {}
        
        # 获取所有ID
        all_ids = set()
        for lang_data in unpickled_data.values():
            all_ids.update(lang_data.keys())
        
        # 合并所有语言的文本
        for entry_id in all_ids:
            combined_data[entry_id] = {}
            
            for lang_code, lang_data in unpickled_data.items():
                if entry_id in lang_data:
                    combined_data[entry_id][lang_code] = lang_data[entry_id]["text"]
        
        return combined_data
    
    def create_en_multi_lang_mapping(self, combined_data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """
        创建英文到多种语言的映射
        使用多级排序：次数 > ID大小，确保结果一致性
        """
        en_to_multi_lang = {}
        en_translations = defaultdict(list)
        
        # 遍历所有条目，统计每个英文文本对应的所有本地化文本
        for entry_id, translations in combined_data.items():
            if "en" in translations:
                en_text = translations["en"]
                entry_id_int = int(entry_id)
                
                # 收集每种语言的翻译，同时记录ID
                for lang_code, lang_text in translations.items():
                    if lang_code != "en":  # 不包含英文本身
                        en_translations[en_text].append((lang_code, lang_text, entry_id_int))
        
        # 处理英文到多种语言的映射
        for en_text, translations_list in en_translations.items():
            # 按语言代码分组
            lang_translations = defaultdict(list)
            for lang_code, lang_text, entry_id in translations_list:
                lang_translations[lang_code].append((lang_text, entry_id))
            
            # 对于每种语言，选择最佳翻译
            multi_lang_translations = {}
            for lang_code, text_id_pairs in lang_translations.items():
                # 统计每个翻译的出现次数和最大ID
                text_counter = Counter()
                max_id_map = {}
                
                for lang_text, entry_id in text_id_pairs:
                    text_counter[lang_text] += 1
                    if lang_text not in max_id_map or entry_id > max_id_map[lang_text]:
                        max_id_map[lang_text] = entry_id
                
                # 多级排序：先按次数降序，再按最大ID降序
                best_text = max(
                    text_counter.keys(),
                    key=lambda x: (text_counter[x], max_id_map[x])
                )
                multi_lang_translations[lang_code] = best_text
            
            # 添加到映射中
            if multi_lang_translations:  # 确保至少有一种其他语言的翻译
                en_to_multi_lang[en_text] = multi_lang_translations
        
        return en_to_multi_lang
    
    def save_json_file(self, data: Any, file_path: Path) -> bool:
        """
        保存JSON文件
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[+] 成功保存到 {file_path}")
            return True
        except Exception as e:
            print(f"[x] 保存到 {file_path} 时出错: {e}")
            return False
    
    def extract_all(self) -> bool:
        """
        执行完整的本地化数据提取流程
        """
        print("[+] 开始本地化数据提取流程...")
        
        # 步骤1: 复制pickle文件到raw目录
        print("\n[+] 步骤1: 复制本地化pickle文件...")
        copied_files = self.copy_localization_pickles_to_raw()
        if not copied_files:
            print("[x] 无法复制pickle文件，请检查EVE客户端是否已安装")
            return False
        
        # 步骤2: 解包pickle文件
        print("\n[+] 步骤2: 解包本地化pickle文件...")
        unpickled_data = self.unpickle_localization_files()
        if not unpickled_data:
            print("[x] 解包pickle文件失败")
            return False
        
        # 步骤3: 创建合并后的本地化数据
        print("\n[+] 步骤3: 创建合并后的本地化数据...")
        combined_data = self.create_combined_localization(unpickled_data)
        
        # 保存合并后的JSON文件
        combined_file = self.output_dir / "combined_localization.json"
        self.save_json_file(combined_data, combined_file)
        
        # 创建英文到多种语言的映射
        print("\n[+] 步骤4: 创建英文到多种语言的映射...")
        en_multi_lang_mapping = self.create_en_multi_lang_mapping(combined_data)
        
        # 保存英文到多种语言的映射
        en_multi_lang_file = self.output_dir / "en_multi_lang_mapping.json"
        self.save_json_file(en_multi_lang_mapping, en_multi_lang_file)
        
        print(f"\n[+] 本地化数据提取完成！")
        print(f"    - 处理了 {len(combined_data)} 个条目")
        print(f"    - 支持 {len(unpickled_data)} 种语言")
        print(f"    - 生成了 {len(en_multi_lang_mapping)} 个英文映射")
        
        return True

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    extractor = LocalizationExtractor(project_root)
    
    success = extractor.extract_all()
    
    if success:
        print("\n[+] 本地化数据提取成功完成！")
        print(f"    输出目录: {extractor.output_dir}")
    else:
        print("\n[x] 本地化数据提取失败！")
        print("    请确保EVE客户端已安装并且SharedCache目录存在")

if __name__ == "__main__":
    main()

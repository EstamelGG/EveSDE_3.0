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
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional, Tuple
from utils.eve_client import EveClient, get_eve_client

class LocalizationExtractor:
    def __init__(self, project_root: Path, eve_client: Optional[EveClient] = None):
        self.project_root = project_root
        self.localization_dir = project_root / "localization"
        self.raw_dir = self.localization_dir / "raw"
        self.extra_dir = self.localization_dir / "extra"
        self.output_dir = self.localization_dir / "output"
        self.eve_client = eve_client or get_eve_client(project_root / "client_cache")
        
        # 创建必要的目录
        self._create_directories()
    
    def _create_directories(self):
        for directory in [self.raw_dir, self.extra_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
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
    
    
    def get_localization_pickles(self) -> Dict[str, str]:
        """
        从 resfileindex 搜索本地化 pickle 并下载到 raw 目录
        """
        pattern = re.compile(r"^res:/localizationfsd/localization_fsd_([\w-]+)\.pickle$", re.I)
        matches = []
        for res_path, entry in self.eve_client.grep(r"^res:/localizationfsd/localization_fsd_"):
            m = pattern.match(res_path)
            if not m:
                continue
            lang_code = m.group(1)
            if lang_code.lower() == "main":
                continue
            if lang_code == "en-us":
                lang_code = "en"
            matches.append((lang_code, res_path, entry.hash))

        if not matches:
            print("[!] 未找到有效的本地化pickle文件")
            return {}

        print(f"[+] 本地化 pickle: {len(matches)} 个语言包")
        res_paths = [res_path for _, res_path, _ in matches]
        self.eve_client.ensure_resources(res_paths, label="本地化")

        result = {}
        downloaded_count = skipped_count = re_downloaded_count = 0

        for lang_code, res_path, expected_hash in matches:
            target_file = self.raw_dir / f"localization_fsd_{lang_code}.pickle"
            entry = self.eve_client.lookup(res_path)
            if not entry:
                continue
            cached = self.eve_client.cache_dir / entry.path
            if not cached.exists():
                continue

            if target_file.exists():
                current_hash = self._calculate_file_hash(target_file)
                if current_hash and current_hash.lower() == expected_hash.lower():
                    result[lang_code] = str(target_file)
                    skipped_count += 1
                    continue
                target_file.unlink(missing_ok=True)
                re_downloaded_count += 1
            else:
                downloaded_count += 1
            shutil.copy2(cached, target_file)
            result[lang_code] = str(target_file)

        if downloaded_count or re_downloaded_count or skipped_count:
            print(f"[+] 本地化: 新 {downloaded_count} / 重下 {re_downloaded_count} / 跳过 {skipped_count}")
        return result
    
    def copy_localization_pickles_to_raw(self) -> Dict[str, str]:
        return self.get_localization_pickles()
    
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
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[x] 保存失败 {file_path}: {e}")
            return False

    def extract_all(self) -> bool:
        copied_files = self.copy_localization_pickles_to_raw()
        if not copied_files:
            print("[x] 未找到本地化 pickle 文件")
            return False

        unpickled_data = self.unpickle_localization_files()
        if not unpickled_data:
            print("[x] 解包 pickle 失败")
            return False

        combined_data = self.create_combined_localization(unpickled_data)
        self.save_json_file(combined_data, self.output_dir / "combined_localization.json")

        en_multi_lang_mapping = self.create_en_multi_lang_mapping(combined_data)
        self.save_json_file(en_multi_lang_mapping, self.output_dir / "en_multi_lang_mapping.json")

        print(f"[+] 本地化完成: {len(combined_data)} 条目, {len(unpickled_data)} 语言")
        return True

def main(eve_client=None):
    """主函数"""
    project_root = Path(__file__).parent.parent
    extractor = LocalizationExtractor(project_root, eve_client=eve_client)
    
    success = extractor.extract_all()
    
    if success:
        print("\n[+] 本地化数据提取成功完成！")
        print(f"    输出目录: {extractor.output_dir}")
    else:
        print("\n[x] 本地化数据提取失败！")
        print("    请确保EVE客户端已安装并且SharedCache目录存在")

if __name__ == "__main__":
    main()

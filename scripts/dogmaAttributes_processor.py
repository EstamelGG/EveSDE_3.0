#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品属性数据处理器模块
用于处理dogmaAttributes数据并写入数据库

对应old版本: old/dogmaAttributes_handler.py
功能: 处理物品属性数据，创建dogmaAttributes表
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
import scripts.icon_finder as icon_finder


class DogmaAttributesProcessor:
    """物品属性数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化dogmaAttributes处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        
        # 单位数据缓存
        self.units_data = {}
        
        # 图标缓存 - 避免重复下载相同图标
        self.icon_cache = {}  # icon_id -> icon_filename映射
        
        # 初始化图标查找器
        self.icon_finder = icon_finder.IconFinder(config)
    
    def read_dogma_units_jsonl(self) -> Dict[str, Any]:
        """
        读取dogmaUnits JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "dogmaUnits.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到dogmaUnits JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取dogmaUnits JSONL文件: {jsonl_file}")
        
        units_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 使用_key作为单位ID
                        unit_id = data['_key']
                        units_data[unit_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(units_data)} 个dogmaUnits记录")
            return units_data
            
        except Exception as e:
            print(f"[x] 读取dogmaUnits JSONL文件时出错: {e}")
            return {}
    
    def read_dogma_attributes_jsonl(self) -> Dict[str, Any]:
        """
        读取dogmaAttributes JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "dogmaAttributes.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到dogmaAttributes JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取dogmaAttributes JSONL文件: {jsonl_file}")
        
        attributes_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为主键
                        key = data['_key']
                        attributes_data[key] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(attributes_data)} 个dogmaAttributes记录")
            return attributes_data
            
        except Exception as e:
            print(f"[x] 读取dogmaAttributes JSONL文件时出错: {e}")
            return {}
    
    def create_dogma_attributes_table(self, cursor: sqlite3.Cursor):
        """
        创建dogmaAttributes表
        完全按照old版本的数据库结构
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dogmaAttributes (
            attribute_id INTEGER NOT NULL PRIMARY KEY,
            categoryID INTEGER,
            name TEXT,
            display_name TEXT,
            tooltipDescription TEXT,
            iconID INTEGER,
            icon_filename TEXT,
            unitID INTEGER,
            unitName TEXT,
            highIsGood BOOLEAN,
            defaultValue REAL,
            stackable BOOLEAN
        )
        ''')
        print("[+] 创建dogmaAttributes表")
    
    def get_icon_filename(self, icon_id: int) -> Optional[str]:
        """
        获取图标文件名
        使用icon_finder从服务器获取图标信息，带缓存机制避免重复下载
        """
        if not icon_id:
            return None
        
        # 检查缓存
        if icon_id in self.icon_cache:
            return self.icon_cache[icon_id]
        
        try:
            # 使用icon_finder获取图标内容并保存到custom_icons目录
            target_filename = f"attribute_{icon_id}.png"
            if self.icon_finder.copy_icon_to_custom_dir(icon_id, target_filename):
                # 缓存成功获取的图标
                self.icon_cache[icon_id] = target_filename
                return target_filename
            else:
                # 如果获取失败，返回默认图标
                default_filename = "attribute_default.png"
                self.icon_cache[icon_id] = default_filename
                return default_filename
        except Exception as e:
            print(f"[!] 获取图标 {icon_id} 时出错: {e}")
            default_filename = "attribute_default.png"
            self.icon_cache[icon_id] = default_filename
            return default_filename
    
    def process_dogma_attributes_to_db(self, attributes_data: Dict[str, Any], cursor: sqlite3.Cursor, language: str):
        """
        处理dogmaAttributes数据并写入数据库
        完全按照old版本的逻辑
        """
        # 用于存储批量插入的数据
        batch_data = []
        batch_size = 1000  # 每批处理的记录数
        
        processed_count = 0
        for key, attr_data in attributes_data.items():
            # 新版本：attributeID字段已移除，使用_key作为attribute_id
            attribute_id = key  # 使用_key作为attribute_id
            # 新版本：categoryID重命名为attributeCategoryID
            category_id = attr_data.get('attributeCategoryID', attr_data.get('categoryID', 0))
            name = attr_data.get('name', None)
            
            # 多语言字段处理
            display_name = None
            if 'displayName' in attr_data and isinstance(attr_data['displayName'], dict):
                display_name = attr_data['displayName'].get(language, None)
            
            tooltip_description = None
            if 'tooltipDescription' in attr_data and isinstance(attr_data['tooltipDescription'], dict):
                tooltip_description = attr_data['tooltipDescription'].get(language, None)
            
            icon_id = attr_data.get('iconID', 0)
            icon_filename = self.get_icon_filename(icon_id)
            
            unit_id = attr_data.get('unitID', None)
            unit_name = None
            
            # 处理单位名称 - 从dogmaUnits数据中获取
            if unit_id is not None and unit_id in self.units_data:
                unit_data = self.units_data[unit_id]
                if 'displayName' in unit_data and isinstance(unit_data['displayName'], dict):
                    unit_name = unit_data['displayName'].get(language, unit_data['displayName'].get('en', None))
            
            high_is_good = attr_data.get('highIsGood', None)
            default_value = attr_data.get('defaultValue', None)
            stackable = attr_data.get('stackable', None)
            
            # 添加到批处理列表
            batch_data.append((
                attribute_id, category_id, name, display_name,
                tooltip_description, icon_id, icon_filename, unit_id, unit_name, 
                high_is_good, default_value, stackable
            ))
            
            processed_count += 1
            
            # 当达到批处理大小时执行插入
            if len(batch_data) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO dogmaAttributes (
                        attribute_id, categoryID, name, display_name, 
                        tooltipDescription, iconID, icon_filename, unitID, unitName, 
                        highIsGood, defaultValue, stackable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
                batch_data = []  # 清空批处理列表
        
        # 处理剩余的数据
        if batch_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO dogmaAttributes (
                    attribute_id, categoryID, name, display_name, 
                    tooltipDescription, iconID, icon_filename, unitID, unitName, 
                    highIsGood, defaultValue, stackable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
        
        print(f"[+] 成功处理 {processed_count} 个dogmaAttributes记录")
        print(f"[+] 图标缓存统计: 缓存了 {len(self.icon_cache)} 个唯一图标")
    
    def process_dogma_attributes_for_language(self, language: str) -> bool:
        """
        为指定语言处理dogmaAttributes数据
        """
        print(f"[+] 开始处理dogmaAttributes数据，语言: {language}")
        
        # 读取dogmaUnits数据（如果还没有加载）
        if not self.units_data:
            self.units_data = self.read_dogma_units_jsonl()
            if not self.units_data:
                print("[!] 无法读取dogmaUnits数据，将跳过单位名称处理")
        
        # 读取dogmaAttributes数据
        attributes_data = self.read_dogma_attributes_jsonl()
        if not attributes_data:
            print("[x] 无法读取dogmaAttributes数据")
            return False
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 创建表
            self.create_dogma_attributes_table(cursor)
            
            # 处理数据
            self.process_dogma_attributes_to_db(attributes_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] dogmaAttributes数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理dogmaAttributes数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理dogmaAttributes数据
        """
        print("[+] 开始处理dogmaAttributes数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_dogma_attributes_for_language(language):
                success_count += 1
        
        print(f"[+] dogmaAttributes数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 物品属性数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DogmaAttributesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品属性数据处理器完成")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品属性详情数据处理器模块
用于处理typeDogma数据并写入数据库

功能: 处理物品属性详情数据，创建typeAttributes、typeEffects和planetResourceHarvest表
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple


class TypeDogmaProcessor:
    """物品属性详情数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化typeDogma处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_type_dogma_jsonl(self) -> Dict[str, Any]:
        """
        读取typeDogma JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "typeDogma.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到typeDogma JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取typeDogma JSONL文件: {jsonl_file}")
        
        dogma_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为type_id
                        type_id = data['_key']
                        dogma_data[type_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(dogma_data)} 个typeDogma记录")
            return dogma_data
            
        except Exception as e:
            print(f"[x] 读取typeDogma JSONL文件时出错: {e}")
            return {}
    
    def create_tables(self, cursor: sqlite3.Cursor):
        """
        创建数据库表
        完全按照old版本的数据库结构
        """
        # 创建typeAttributes表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS typeAttributes (
            type_id INTEGER NOT NULL,
            attribute_id INTEGER NOT NULL,
            value REAL,
            unitID INTEGER,
            PRIMARY KEY (type_id, attribute_id)
        )
        ''')
        
        # 创建typeEffects表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS typeEffects (
            type_id INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            is_default BOOLEAN,
            PRIMARY KEY (type_id, effect_id)
        )
        ''')
        
        # 创建planetResourceHarvest表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS planetResourceHarvest (
            typeid INTEGER NOT NULL,
            harvest_typeid INTEGER NOT NULL,
            PRIMARY KEY (typeid, harvest_typeid)
        )
        ''')
        
        print("[+] 创建typeAttributes、typeEffects和planetResourceHarvest表")
    
    def get_attribute_unit_mapping(self, cursor: sqlite3.Cursor) -> Dict[int, int]:
        """
        获取dogmaAttributes表中的attribute_id和unitID映射
        完全按照old版本的逻辑
        """
        try:
            cursor.execute('''
                SELECT attribute_id, unitID
                FROM dogmaAttributes
                WHERE unitID IS NOT NULL
            ''')
            return dict(cursor.fetchall())
        except Exception as e:
            print(f"[!] 获取属性单位映射时出错: {e}")
            return {}
    
    def process_type_dogma_to_db(self, dogma_data: Dict[str, Any], cursor: sqlite3.Cursor, language: str):
        """
        处理typeDogma数据并写入数据库
        完全按照old版本的逻辑
        """
        # 获取属性单位映射
        attribute_unit_map = self.get_attribute_unit_mapping(cursor)
        
        # 用于批量插入的数据
        attribute_batch = []
        effect_batch = []
        harvest_batch = []
        batch_size = 1000
        
        processed_types = 0
        processed_attributes = 0
        processed_effects = 0
        processed_harvests = 0
        
        # 按type_id排序处理，确保插入顺序一致
        for type_id in sorted(dogma_data.keys()):
            details = dogma_data[type_id]
            # 处理dogmaAttributes数据
            if 'dogmaAttributes' in details:
                # 按attribute_id排序，确保插入顺序一致
                for attribute in sorted(details['dogmaAttributes'], key=lambda x: x['attributeID']):
                    attribute_id = attribute['attributeID']
                    value = attribute['value']
                    unit_id = attribute_unit_map.get(attribute_id)  # 获取对应的unitID
                    
                    attribute_batch.append((type_id, attribute_id, value, unit_id))
                    processed_attributes += 1
                    
                    # 特殊处理attribute_id = 709的情况
                    if attribute_id == 709:
                        harvest_typeid = int(value)
                        harvest_batch.append((harvest_typeid, type_id))
                        processed_harvests += 1
                    
                    # 当达到批处理大小时执行插入
                    if len(attribute_batch) >= batch_size:
                        cursor.executemany('''
                            INSERT OR REPLACE INTO typeAttributes (type_id, attribute_id, value, unitID)
                            VALUES (?, ?, ?, ?)
                        ''', attribute_batch)
                        attribute_batch = []
            
            # 处理dogmaEffects数据
            if 'dogmaEffects' in details:
                # 按effect_id排序，确保插入顺序一致
                for effect in sorted(details['dogmaEffects'], key=lambda x: x['effectID']):
                    effect_batch.append((type_id, effect['effectID'], effect['isDefault']))
                    processed_effects += 1
                    
                    # 当达到批处理大小时执行插入
                    if len(effect_batch) >= batch_size:
                        cursor.executemany('''
                            INSERT OR REPLACE INTO typeEffects (type_id, effect_id, is_default)
                            VALUES (?, ?, ?)
                        ''', effect_batch)
                        effect_batch = []
            
            # 处理planetResourceHarvest数据
            if harvest_batch and len(harvest_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO planetResourceHarvest (typeid, harvest_typeid)
                    VALUES (?, ?)
                ''', harvest_batch)
                harvest_batch = []
            
            processed_types += 1
        
        # 处理剩余的批量数据
        if attribute_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO typeAttributes (type_id, attribute_id, value, unitID)
                VALUES (?, ?, ?, ?)
            ''', attribute_batch)
        
        if effect_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO typeEffects (type_id, effect_id, is_default)
                VALUES (?, ?, ?)
            ''', effect_batch)
        
        if harvest_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO planetResourceHarvest (typeid, harvest_typeid)
                VALUES (?, ?)
            ''', harvest_batch)
        
        print(f"[+] 成功处理 {processed_types} 个类型，{processed_attributes} 个属性，{processed_effects} 个效果，{processed_harvests} 个收获记录")
    
    def process_type_dogma_for_language(self, language: str) -> bool:
        """
        为指定语言处理typeDogma数据
        """
        print(f"[+] 开始处理typeDogma数据，语言: {language}")
        
        # 读取typeDogma数据
        dogma_data = self.read_type_dogma_jsonl()
        if not dogma_data:
            print("[x] 无法读取typeDogma数据")
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
            self.create_tables(cursor)
            
            # 处理数据
            self.process_type_dogma_to_db(dogma_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] typeDogma数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理typeDogma数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理typeDogma数据
        """
        print("[+] 开始处理typeDogma数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_type_dogma_for_language(language):
                success_count += 1
        
        print(f"[+] typeDogma数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 物品属性详情数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = TypeDogmaProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品属性详情数据处理器完成")


if __name__ == "__main__":
    main()

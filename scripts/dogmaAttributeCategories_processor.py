#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品属性目录数据处理器模块
用于处理dogmaAttributeCategories数据并写入数据库

功能: 处理物品属性目录数据，创建dogmaAttributeCategories表
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any


class DogmaAttributeCategoriesProcessor:
    """物品属性目录数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化dogmaAttributeCategories处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        
        # 语言映射表，完全按照old版本的映射
        self.language_map = {
            "Fitting": {
                "zh": "装配"
            },
            "Shield": {
                "zh": "护盾"
            },
            "Armor": {
                "zh": "装甲"
            },
            "Structure": {
                "zh": "结构"
            },
            "Capacitor": {
                "zh": "电容"
            },
            "Targeting": {
                "zh": "目标锁定"
            },
            "Miscellaneous": {
                "zh": "杂项"
            },
            "Required Skills": {
                "zh": "所需技能"
            },
            "Drones": {
                "zh": "无人机"
            },
            "AI": {
                "zh": "AI"
            },
            "Speed and Travel": {
                "zh": "速度与旅行"
            },
            "Loot": {
                "zh": "战利品"
            },
            "Remote Assistance": {
                "zh": "远程协助"
            },
            "EW - Target Painting": {
                "zh": "电子战-目标标记"
            },
            "EW - Energy Neutralizing": {
                "zh": "电子战-能量中和"
            },
            "EW - Remote Electronic Counter Measures": {
                "zh": "电子战-电子干扰"
            },
            "EW - Sensor Dampening": {
                "zh": "电子战-感应抑阻"
            },
            "EW - Target Jamming": {
                "zh": "电子战-锁定干扰"
            },
            "EW - Tracking Disruption": {
                "zh": "电子战-索敌扰断"
            },
            "EW - Warp Scrambling": {
                "zh": "电子战-跃迁扰断"
            },
            "EW - Webbing": {
                "zh": "电子战-停滞网"
            },
            "Turrets": {
                "zh": "炮塔"
            },
            "Missile": {
                "zh": "导弹"
            },
            "Graphics": {
                "zh": "图形"
            },
            "Entity Rewards": {
                "zh": "赏金"
            },
            "Entity Extra Attributes": {
                "zh": "附加属性"
            },
            "Fighter Abilities": {
                "zh": "舰载机能力"
            },
            "EW - Resistance": {
                "zh": "电子战抗性"
            },
            "Bonuses": {
                "zh": "加成"
            },
            "Fighter Attributes": {
                "zh": "舰载机属性"
            },
            "Superweapons": {
                "zh": "超级武器"
            },
            "Hangars & Bays": {
                "zh": "船舱"
            },
            "On Death": {
                "zh": "死亡时"
            },
            "Behavior Attributes": {
                "zh": "行为属性"
            },
            "Mining": {
                "zh": "采矿"
            },
            "Heat": {
                "zh": "超载"
            }
        }
    
    def read_dogma_attribute_categories_jsonl(self) -> Dict[str, Any]:
        """
        读取dogmaAttributeCategories JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "dogmaAttributeCategories.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到dogmaAttributeCategories JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取dogmaAttributeCategories JSONL文件: {jsonl_file}")
        
        categories_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为category_id
                        category_id = data['_key']
                        categories_data[category_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(categories_data)} 个dogmaAttributeCategories记录")
            return categories_data
            
        except Exception as e:
            print(f"[x] 读取dogmaAttributeCategories JSONL文件时出错: {e}")
            return {}
    
    def create_dogma_attribute_categories_table(self, cursor: sqlite3.Cursor):
        """
        创建dogmaAttributeCategories表
        完全按照old版本的数据库结构
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dogmaAttributeCategories (
            attribute_category_id INTEGER NOT NULL PRIMARY KEY,
            name TEXT,
            description TEXT
        )
        ''')
        print("[+] 创建dogmaAttributeCategories表")
    
    def process_dogma_attribute_categories_to_db(self, categories_data: Dict[str, Any], cursor: sqlite3.Cursor, language: str):
        """
        处理dogmaAttributeCategories数据并写入数据库
        完全按照old版本的逻辑
        """
        # 处理每个属性目录
        processed_count = 0
        for category_id, category_data in categories_data.items():
            # 获取字段
            name = category_data.get('name', "")
            description = category_data.get('description', "")
            
            # 应用语言映射
            if name in self.language_map.keys():
                if language in self.language_map[name]:
                    name = self.language_map[name][language]
            
            # 插入数据
            cursor.execute('''
                INSERT OR REPLACE INTO dogmaAttributeCategories (
                    attribute_category_id, name, description
                ) VALUES (?, ?, ?)
            ''', (category_id, name, description))
            
            processed_count += 1
        
        print(f"[+] 成功处理 {processed_count} 个dogmaAttributeCategories记录")
    
    def process_dogma_attribute_categories_for_language(self, language: str) -> bool:
        """
        为指定语言处理dogmaAttributeCategories数据
        """
        print(f"[+] 开始处理dogmaAttributeCategories数据，语言: {language}")
        
        # 读取dogmaAttributeCategories数据
        categories_data = self.read_dogma_attribute_categories_jsonl()
        if not categories_data:
            print("[x] 无法读取dogmaAttributeCategories数据")
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
            self.create_dogma_attribute_categories_table(cursor)
            
            # 处理数据
            self.process_dogma_attribute_categories_to_db(categories_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] dogmaAttributeCategories数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理dogmaAttributeCategories数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理dogmaAttributeCategories数据
        """
        print("[+] 开始处理dogmaAttributeCategories数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_dogma_attribute_categories_for_language(language):
                success_count += 1
        
        print(f"[+] dogmaAttributeCategories数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 物品属性目录数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DogmaAttributeCategoriesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品属性目录数据处理器完成")


if __name__ == "__main__":
    main()

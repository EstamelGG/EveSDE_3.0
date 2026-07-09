#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
类型特性处理器模块
处理EVE类型特性数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
import scripts.jsonl_loader as jsonl_loader


class TypeTraitsProcessor:
    """EVE类型特性处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化类型特性处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.type_bonus_data = {}
    
    def load_type_bonus_data(self):
        """加载类型加成数据"""
        print("[+] 加载类型加成数据...")
        
        # 加载typeBonus数据
        type_bonus_file = self.sde_input_path / "typeBonus.jsonl"
        if type_bonus_file.exists():
            type_bonus_list = jsonl_loader.load_jsonl(str(type_bonus_file))
            self.type_bonus_data = {item['_key']: item for item in type_bonus_list}
            print(f"[+] 加载了 {len(self.type_bonus_data)} 个类型加成")
        else:
            print(f"[x] 文件不存在: {type_bonus_file}")
    
    def process_single_data(self, type_id: int, traits_data: Dict[str, Any], language: str = 'en') -> List[Tuple]:
        """处理单个物品的traits数据"""
        results = []
        
        # 处理 roleBonuses
        if 'roleBonuses' in traits_data:
            for bonus in traits_data['roleBonuses']:
                content = None
                if 'bonusText' in bonus:
                    content = bonus['bonusText'].get(language, '')
                    if not content:  # 如果当前语言的内容为空，使用英语
                        content = bonus['bonusText'].get('en', '')
                    
                    if content:  # 只有在有内容的情况下才处理
                        # 如果有bonus和unitID，需要添加到文本前面
                        if 'bonus' in bonus and 'unitID' in bonus:
                            bonus_num = int(bonus['bonus']) if isinstance(bonus['bonus'], int) or bonus['bonus'].is_integer() else round(bonus['bonus'], 2)
                            if bonus['unitID'] == 105:  # 百分比
                                prefix = f"<b>{bonus_num}%</b> "
                            elif bonus['unitID'] == 104:  # 倍乘
                                prefix = f"<b>{bonus_num}x</b> "
                            elif bonus['unitID'] == 139:  # 加号
                                prefix = f"<b>{bonus_num}+</b> "
                            else:
                                prefix = f"<b>{bonus_num}</b> "
                            content = prefix + content
                        
                        results.append((type_id, content, -1, bonus.get('importance', 999999), "roleBonuses"))
        
        # 处理 typeBonuses
        if 'types' in traits_data:
            for skill_bonus in traits_data['types']:
                skill_id = skill_bonus['_key']
                skill_bonuses = skill_bonus['_value']
                for bonus in skill_bonuses:
                    content = None
                    if 'bonusText' in bonus:
                        content = bonus['bonusText'].get(language, '')
                        if not content:  # 如果当前语言的内容为空，使用英语
                            content = bonus['bonusText'].get('en', '')
                        
                        if content:  # 只有在有内容的情况下才处理
                            # 如果有bonus和unitID，需要添加到文本前面
                            if 'bonus' in bonus and 'unitID' in bonus:
                                bonus_num = int(bonus['bonus']) if isinstance(bonus['bonus'], int) or bonus['bonus'].is_integer() else round(bonus['bonus'], 2)
                                if bonus['unitID'] == 105:  # 百分比
                                    prefix = f"<b>{bonus_num}%</b> "
                                elif bonus['unitID'] == 104:  # 倍乘
                                    prefix = f"<b>{bonus_num}x</b> "
                                elif bonus['unitID'] == 139:  # 加号
                                    prefix = f"<b>{bonus_num}+</b> "
                                else:
                                    prefix = f"<b>{bonus_num}</b> "
                                content = prefix + content
                            
                            results.append((type_id, content, skill_id, bonus.get('importance', 999999), "typeBonuses"))
        
        # 处理 miscBonuses
        if 'miscBonuses' in traits_data:
            for bonus in traits_data['miscBonuses']:
                content = None
                if 'bonusText' in bonus:
                    content = bonus['bonusText'].get(language, '')
                    if not content:  # 如果当前语言的内容为空，使用英语
                        content = bonus['bonusText'].get('en', '')
                    
                    if content:  # 只有在有内容的情况下才处理
                        # 如果有bonus和unitID，需要添加到文本前面
                        if 'bonus' in bonus and 'unitID' in bonus:
                            bonus_num = int(bonus['bonus']) if isinstance(bonus['bonus'], int) or bonus['bonus'].is_integer() else round(bonus['bonus'], 2)
                            if bonus['unitID'] == 105:  # 百分比
                                prefix = f"<b>{bonus_num}%</b> "
                            elif bonus['unitID'] == 104:  # 倍乘
                                prefix = f"<b>{bonus_num}x</b> "
                            elif bonus['unitID'] == 139:  # 加号
                                prefix = f"<b>{bonus_num}+</b> "
                            else:
                                prefix = f"<b>{bonus_num}</b> "
                            content = prefix + content
                        
                        results.append((type_id, content, -1, bonus.get('importance', 999999), "miscBonuses"))
        
        # 按importance排序
        return sorted(results, key=lambda x: x[3])
    
    def create_traits_table(self, cursor: sqlite3.Cursor):
        """创建traits表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS traits (
                typeid INTEGER NOT NULL,
                content TEXT NOT NULL,
                skill INTEGER NOT NULL DEFAULT -1,
                importance INTEGER,
                bonus_type TEXT,
                PRIMARY KEY (typeid, content, skill)
            )
        ''')
    
    def process_traits_to_db(self, cursor: sqlite3.Cursor, language: str = 'en'):
        """处理traits数据并插入数据库"""
        print(f"[+] 开始处理traits数据 (语言: {language})...")
        
        # 创建表
        self.create_traits_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM traits')
        
        # 处理每个物品的traits数据
        for type_id, type_data in self.type_bonus_data.items():
            traits = self.process_single_data(type_id, type_data, language)
            for type_id, content, skill, importance, bonus_type in traits:
                # 逐个插入
                cursor.execute(
                    'INSERT OR REPLACE INTO traits (typeid, content, skill, importance, bonus_type) VALUES (?, ?, ?, ?, ?)',
                    (type_id, content, skill, importance, bonus_type)
                )
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM traits')
        traits_count = cursor.fetchone()[0]
        print(f"[+] traits数据处理完成: {traits_count} 个")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载数据
        self.load_type_bonus_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理traits数据
                self.process_traits_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 类型特性处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = TypeTraitsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 类型特性处理器完成")


if __name__ == "__main__":
    main()

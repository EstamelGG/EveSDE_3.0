#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行星制造处理器模块
处理EVE行星制造数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class PlanetSchematicsProcessor:
    """EVE行星制造处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化行星制造处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.planet_schematics_data = {}
    
    def load_planet_schematics_data(self):
        """加载行星制造数据"""
        print("[+] 加载行星制造数据...")
        
        # 加载行星制造数据
        schematics_file = self.sde_input_path / "planetSchematics.jsonl"
        schematics_list = jsonl_loader.load_jsonl(str(schematics_file))
        self.planet_schematics_data = {item['_key']: item for item in schematics_list}
        print(f"[+] 加载了 {len(self.planet_schematics_data)} 个行星制造方案")
    
    def create_planet_schematics_table(self, cursor: sqlite3.Cursor):
        """创建planetSchematics表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planetSchematics (
                schematic_id INTEGER NOT NULL,
                output_typeid INTEGER NOT NULL PRIMARY KEY,
                name TEXT,
                facilitys TEXT,
                cycle_time INTEGER,
                output_value INTEGER,
                input_typeid TEXT,
                input_value TEXT
            )
        ''')
    
    def process_planet_schematics_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理行星制造数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理行星制造数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_planet_schematics_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM planetSchematics')
        
        # 处理行星制造数据
        schematics_batch = []
        batch_size = 100  # 行星制造数据量不大，使用较小的批次
        
        for schematic_id, schematic_data in self.planet_schematics_data.items():
            # 获取基本信息
            cycle_time = schematic_data.get('cycleTime', 0)
            
            # 获取多语言名称
            name_dict = schematic_data.get('name', {})
            name = name_dict.get(lang, name_dict.get('en', ''))
            
            # 获取设施列表
            pins = schematic_data.get('pins', [])
            facilitys = ','.join(map(str, pins))
            
            # 处理输入输出类型
            input_typeids = []
            input_values = []
            output_typeid = None
            output_value = None
            
            types_data = schematic_data.get('types', [])
            for type_item in types_data:
                type_id = type_item.get('_key')
                quantity = type_item.get('quantity', 0)
                is_input = type_item.get('isInput', False)
                
                if is_input:
                    input_typeids.append(str(type_id))
                    input_values.append(str(quantity))
                else:
                    output_typeid = type_id
                    output_value = quantity
            
            # 将输入类型和数量转换为字符串
            input_typeid_str = ','.join(input_typeids)
            input_value_str = ','.join(input_values)
            
            schematics_batch.append((
                schematic_id, output_typeid, name, facilitys, 
                cycle_time, output_value, input_typeid_str, input_value_str
            ))
            
            # 批量插入
            if len(schematics_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO planetSchematics (
                        schematic_id, output_typeid, name, facilitys, cycle_time, 
                        output_value, input_typeid, input_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', schematics_batch)
                schematics_batch = []
        
        # 处理剩余的数据
        if schematics_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO planetSchematics (
                    schematic_id, output_typeid, name, facilitys, cycle_time, 
                    output_value, input_typeid, input_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', schematics_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM planetSchematics')
        schematics_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] 行星制造数据处理完成:")
        print(f"    - 制造方案: {schematics_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载行星制造数据
        self.load_planet_schematics_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理行星制造数据
                self.process_planet_schematics_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 行星制造处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = PlanetSchematicsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 行星制造处理器完成")


if __name__ == "__main__":
    main()

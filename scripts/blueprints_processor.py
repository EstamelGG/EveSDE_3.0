#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蓝图数据处理器模块
用于处理blueprints数据并写入数据库

功能: 处理蓝图数据，创建多个蓝图相关表
完全按照old版本的逻辑实现，确保数据库结构一致
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


class BlueprintsProcessor:
    """蓝图数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化blueprints处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_blueprints_jsonl(self) -> Dict[str, Any]:
        """
        读取blueprints JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "blueprints.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到blueprints JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取blueprints JSONL文件: {jsonl_file}")
        
        blueprints_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为blueprint_id
                        blueprint_id = data['_key']
                        blueprints_data[blueprint_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(blueprints_data)} 个blueprints记录")
            return blueprints_data
            
        except Exception as e:
            print(f"[x] 读取blueprints JSONL文件时出错: {e}")
            return {}
    
    def get_type_name(self, cursor: sqlite3.Cursor, type_id: int) -> Optional[str]:
        """从types表获取类型名称"""
        cursor.execute('SELECT name FROM types WHERE type_id = ?', (type_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_type_icon(self, cursor: sqlite3.Cursor, type_id: int) -> Optional[str]:
        """从types表获取类型图标"""
        cursor.execute('SELECT icon_filename FROM types WHERE type_id = ?', (type_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_bpc_icon(self, cursor: sqlite3.Cursor, type_id: int) -> Optional[str]:
        """从types表获取BPC图标"""
        cursor.execute('SELECT bpc_icon_filename FROM types WHERE type_id = ?', (type_id,))
        result = cursor.fetchone()
        return result[0] if result else self.get_type_icon(cursor, type_id)
    
    def create_tables(self, cursor: sqlite3.Cursor):
        """创建所需的数据表"""
        # 制造材料表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_manufacturing_materials (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 制造产出表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_manufacturing_output (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')

        # 制造技能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_manufacturing_skills (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            level INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')

        # 材料研究材料表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_research_material_materials (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 材料研究技能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_research_material_skills (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            level INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 时间研究材料表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_research_time_materials (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 时间研究技能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_research_time_skills (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            level INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 复制材料表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_copying_materials (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 复制技能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_copying_skills (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            level INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 发明材料表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_invention_materials (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 发明产出表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_invention_products (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            quantity INTEGER,
            probability REAL,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 发明技能表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_invention_skills (
            blueprintTypeID INTEGER NOT NULL,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            typeName TEXT,
            typeIcon TEXT,
            level INTEGER,
            PRIMARY KEY (blueprintTypeID, typeID)
        )
        ''')
        
        # 处理时间表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blueprint_process_time (
            blueprintTypeID INTEGER NOT NULL PRIMARY KEY,
            blueprintTypeName TEXT,
            blueprintTypeIcon TEXT,
            manufacturing_time INTEGER,
            research_material_time INTEGER,
            research_time_time INTEGER,
            copying_time INTEGER,
            invention_time INTEGER,
            maxRunsPerCopy INTEGER
        )
        ''')
        
        print("[+] 创建蓝图相关表")
    
    def clear_tables(self, cursor: sqlite3.Cursor):
        """清空所有相关表"""
        tables = [
            'blueprint_manufacturing_materials',
            'blueprint_manufacturing_output',
            'blueprint_research_material_materials',
            'blueprint_research_material_skills',
            'blueprint_manufacturing_skills',
            'blueprint_research_time_materials',
            'blueprint_research_time_skills',
            'blueprint_copying_materials',
            'blueprint_copying_skills',
            'blueprint_invention_materials',
            'blueprint_invention_products',
            'blueprint_invention_skills',
            'blueprint_process_time'
        ]
        for table in tables:
            cursor.execute(f'DELETE FROM {table}')
    
    def process_blueprints_to_db(self, blueprints_data: Dict[str, Any], cursor: sqlite3.Cursor, lang: str):
        """
        处理blueprints数据并写入数据库
        完全按照old版本的逻辑
        """
        try:
            # 创建表
            self.create_tables(cursor)
            # 清空表
            self.clear_tables(cursor)
            
            for blueprint_id, blueprint_data in blueprints_data.items():
                try:
                    blueprint_type_id = blueprint_data['blueprintTypeID']
                    blueprint_type_name = self.get_type_name(cursor, blueprint_type_id)
                    blueprint_type_icon = self.get_type_icon(cursor, blueprint_type_id)
                    activities = blueprint_data.get('activities', {})
                    maxProductionLimit = blueprint_data.get('maxProductionLimit', 0)

                    # 记录处理时间
                    times = {
                        'manufacturing_time': (activities.get('manufacturing') or activities.get('reaction') or {}).get('time', 0),
                        'research_material_time': activities.get('research_material', {}).get('time', 0),
                        'research_time_time': activities.get('research_time', {}).get('time', 0),
                        'copying_time': activities.get('copying', {}).get('time', 0),
                        'invention_time': activities.get('invention', {}).get('time', 0)
                    }
                    cursor.execute(
                        'INSERT OR REPLACE INTO blueprint_process_time (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, manufacturing_time, research_material_time, research_time_time, copying_time, invention_time, maxRunsPerCopy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, times['manufacturing_time'], times['research_material_time'], times['research_time_time'], times['copying_time'], times['invention_time'], maxProductionLimit)
                    )
                    
                    # 处理制造
                    if 'manufacturing' in activities or "reaction" in activities:
                        if "manufacturing" in activities:
                            mfg = activities['manufacturing']
                        else:
                            mfg = activities['reaction']
                        # 处理材料
                        if 'materials' in mfg:
                            for material in mfg['materials']:
                                if "typeID" in material:
                                    type_id = material['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_manufacturing_materials (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, material.get("quantity", -1))
                                    )
                        # 处理产出
                        if 'products' in mfg:
                            for product in mfg['products']:
                                if "typeID" in product:
                                    type_id = product['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_manufacturing_output (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, product.get("quantity", -1))
                                    )
                        # 处理技能
                        if 'skills' in mfg:
                            for skill in mfg['skills']:
                                if "typeID" in skill:
                                    type_id = skill['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_manufacturing_skills (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, level) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, skill.get("level", -1))
                                    )
                    
                    # 处理材料研究
                    if 'research_material' in activities:
                        rm = activities['research_material']
                        # 处理材料
                        if 'materials' in rm:
                            for material in rm['materials']:
                                if "typeID" in material:
                                    type_id = material['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_research_material_materials (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, material.get("quantity", -1))
                                    )
                        # 处理技能
                        if 'skills' in rm:
                            for skill in rm['skills']:
                                if "typeID" in skill:
                                    type_id = skill['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_research_material_skills (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, level) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, skill.get("level", -1))
                                    )
                    
                    # 处理时间研究
                    if 'research_time' in activities:
                        rt = activities['research_time']
                        # 处理材料
                        if 'materials' in rt:
                            for material in rt['materials']:
                                if "typeID" in material:
                                    type_id = material['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_research_time_materials (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, material.get("quantity", -1))
                                    )
                        # 处理技能
                        if 'skills' in rt:
                            for skill in rt['skills']:
                                if "typeID" in skill:
                                    type_id = skill['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_research_time_skills (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, level) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, skill.get("level", -1))
                                    )
                    
                    # 处理复制
                    if 'copying' in activities:
                        cp = activities['copying']
                        # 处理材料
                        if 'materials' in cp:
                            for material in cp['materials']:
                                if "typeID" in material:
                                    type_id = material['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_copying_materials (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, material.get("quantity", -1))
                                    )
                        # 处理技能
                        if 'skills' in cp:
                            for skill in cp['skills']:
                                if "typeID" in skill:
                                    type_id = skill['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_copying_skills (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, level) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, skill.get("level", -1))
                                    )
                    
                    # 处理发明
                    if 'invention' in activities:
                        inv = activities['invention']
                        # 处理材料
                        if 'materials' in inv:
                            for material in inv['materials']:
                                if "typeID" in material:
                                    type_id = material['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_invention_materials (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, material.get("quantity", -1))
                                    )
                        # 处理蓝图发明产出
                        if 'products' in inv:
                            for product in inv['products']:
                                if "typeID" in product:
                                    type_id = product['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_bpc_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_invention_products (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, quantity, probability) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, product.get("quantity", -1), product.get("probability", 0))
                                    )
                        # 处理技能
                        if 'skills' in inv:
                            for skill in inv['skills']:
                                if "typeID" in skill:
                                    type_id = skill['typeID']
                                    type_name = self.get_type_name(cursor, type_id)
                                    type_icon = self.get_type_icon(cursor, type_id)
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO blueprint_invention_skills (blueprintTypeID, blueprintTypeName, blueprintTypeIcon, typeID, typeName, typeIcon, level) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (blueprint_type_id, blueprint_type_name, blueprint_type_icon, type_id, type_name, type_icon, skill.get("level", -1))
                                    )
                
                except Exception as e:
                    print(f"[!] 处理蓝图 {blueprint_id} 时出错: {str(e)}")
                    continue

            print(f"[+] 已处理 {len(blueprints_data)} 个蓝图数据，语言: {lang}")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_blueprints_for_language(self, language: str) -> bool:
        """
        为指定语言处理blueprints数据
        """
        print(f"[+] 开始处理blueprints数据，语言: {language}")
        
        # 读取blueprints数据
        blueprints_data = self.read_blueprints_jsonl()
        if not blueprints_data:
            print("[x] 无法读取blueprints数据")
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
            
            # 处理数据
            self.process_blueprints_to_db(blueprints_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] blueprints数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理blueprints数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理blueprints数据
        """
        print("[+] 开始处理blueprints数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_blueprints_for_language(language):
                success_count += 1
        
        print(f"[+] blueprints数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 蓝图数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = BlueprintsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 蓝图数据处理器完成")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蓝图数据处理器模块
用于处理blueprints数据并写入数据库

功能: 处理蓝图数据，创建多个蓝图相关表
完全按照old版本的逻辑实现，确保数据库结构一致
"""

from utils.single_db import get_db_path
from utils.wide_i18n import LANGS, names_ddl, names_row, name_cols_sql
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
    
    def get_type_names(self, cursor: sqlite3.Cursor, type_id: int) -> Dict[str, str]:
        cursor.execute(f'SELECT {name_cols_sql()} FROM types WHERE type_id = ?', (type_id,))
        row = cursor.fetchone()
        if not row:
            return {lang: "" for lang in LANGS}
        return {LANGS[i]: row[i] or "" for i in range(len(LANGS))}

    def insert_dual_type_row(
        self,
        cursor: sqlite3.Cursor,
        table: str,
        bp_id: int,
        bp_names: Dict[str, str],
        bp_icon: Optional[str],
        type_id: int,
        type_names: Dict[str, str],
        type_icon: Optional[str],
        extra_columns: str = "",
        extra_values: Tuple = (),
    ):
        bp_cols = name_cols_sql("blueprint")
        type_cols = name_cols_sql("type")
        columns = f"blueprintTypeID, {bp_cols}, blueprintTypeIcon, typeID, {type_cols}, typeIcon"
        values: List = [bp_id, *names_row(bp_names), bp_icon, type_id, *names_row(type_names), type_icon]
        if extra_columns:
            columns += f", {extra_columns}"
            values.extend(extra_values)
        placeholders = ", ".join(["?"] * len(values))
        cursor.execute(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})", values)

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
        dual = lambda extra, pk: f'''
        CREATE TABLE IF NOT EXISTS {{name}} (
            blueprintTypeID INTEGER NOT NULL,
            {names_ddl("blueprint")},
            blueprintTypeIcon TEXT,
            typeID INTEGER NOT NULL,
            {names_ddl("type")},
            typeIcon TEXT,
            {extra}
            {pk}
        )'''
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_manufacturing_materials"))
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_manufacturing_output"))
        cursor.execute(dual("level INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_manufacturing_skills"))
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_research_material_materials"))
        cursor.execute(dual("level INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_research_material_skills"))
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_research_time_materials"))
        cursor.execute(dual("level INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_research_time_skills"))
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_copying_materials"))
        cursor.execute(dual("level INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_copying_skills"))
        cursor.execute(dual("quantity INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_invention_materials"))
        cursor.execute(dual("quantity INTEGER, probability REAL", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_invention_products"))
        cursor.execute(dual("level INTEGER", "PRIMARY KEY (blueprintTypeID, typeID)").format(name="blueprint_invention_skills"))
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS blueprint_process_time (
            blueprintTypeID INTEGER NOT NULL PRIMARY KEY,
            {names_ddl("blueprint")},
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
    
    def process_blueprints_to_db(self, blueprints_data: Dict[str, Any], cursor: sqlite3.Cursor):
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
                    bp_names = self.get_type_names(cursor, blueprint_type_id)
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
                        f'''INSERT OR REPLACE INTO blueprint_process_time
                        (blueprintTypeID, {name_cols_sql("blueprint")}, blueprintTypeIcon,
                         manufacturing_time, research_material_time, research_time_time,
                         copying_time, invention_time, maxRunsPerCopy)
                        VALUES (?, {", ".join(["?"] * 8)}, ?, ?, ?, ?, ?, ?, ?)''',
                        (blueprint_type_id, *names_row(bp_names), blueprint_type_icon,
                         times['manufacturing_time'], times['research_material_time'],
                         times['research_time_time'], times['copying_time'],
                         times['invention_time'], maxProductionLimit),
                    )
                    
                    def add_row(table, type_id, type_icon, extra_columns="", extra_values=()):
                        type_names = self.get_type_names(cursor, type_id)
                        self.insert_dual_type_row(
                            cursor, table, blueprint_type_id, bp_names, blueprint_type_icon,
                            type_id, type_names, type_icon, extra_columns, extra_values,
                        )

                    # 处理制造
                    if 'manufacturing' in activities or "reaction" in activities:
                        mfg = activities.get('manufacturing') or activities.get('reaction')
                        for material in mfg.get('materials', []):
                            if "typeID" in material:
                                add_row('blueprint_manufacturing_materials', material['typeID'],
                                        self.get_type_icon(cursor, material['typeID']),
                                        'quantity', (material.get("quantity", -1),))
                        for product in mfg.get('products', []):
                            if "typeID" in product:
                                add_row('blueprint_manufacturing_output', product['typeID'],
                                        self.get_type_icon(cursor, product['typeID']),
                                        'quantity', (product.get("quantity", -1),))
                        for skill in mfg.get('skills', []):
                            if "typeID" in skill:
                                add_row('blueprint_manufacturing_skills', skill['typeID'],
                                        self.get_type_icon(cursor, skill['typeID']),
                                        'level', (skill.get("level", -1),))

                    if 'research_material' in activities:
                        rm = activities['research_material']
                        for material in rm.get('materials', []):
                            if "typeID" in material:
                                add_row('blueprint_research_material_materials', material['typeID'],
                                        self.get_type_icon(cursor, material['typeID']),
                                        'quantity', (material.get("quantity", -1),))
                        for skill in rm.get('skills', []):
                            if "typeID" in skill:
                                add_row('blueprint_research_material_skills', skill['typeID'],
                                        self.get_type_icon(cursor, skill['typeID']),
                                        'level', (skill.get("level", -1),))

                    if 'research_time' in activities:
                        rt = activities['research_time']
                        for material in rt.get('materials', []):
                            if "typeID" in material:
                                add_row('blueprint_research_time_materials', material['typeID'],
                                        self.get_type_icon(cursor, material['typeID']),
                                        'quantity', (material.get("quantity", -1),))
                        for skill in rt.get('skills', []):
                            if "typeID" in skill:
                                add_row('blueprint_research_time_skills', skill['typeID'],
                                        self.get_type_icon(cursor, skill['typeID']),
                                        'level', (skill.get("level", -1),))

                    if 'copying' in activities:
                        cp = activities['copying']
                        for material in cp.get('materials', []):
                            if "typeID" in material:
                                add_row('blueprint_copying_materials', material['typeID'],
                                        self.get_type_icon(cursor, material['typeID']),
                                        'quantity', (material.get("quantity", -1),))
                        for skill in cp.get('skills', []):
                            if "typeID" in skill:
                                add_row('blueprint_copying_skills', skill['typeID'],
                                        self.get_type_icon(cursor, skill['typeID']),
                                        'level', (skill.get("level", -1),))

                    if 'invention' in activities:
                        inv = activities['invention']
                        for material in inv.get('materials', []):
                            if "typeID" in material:
                                add_row('blueprint_invention_materials', material['typeID'],
                                        self.get_type_icon(cursor, material['typeID']),
                                        'quantity', (material.get("quantity", -1),))
                        for product in inv.get('products', []):
                            if "typeID" in product:
                                add_row('blueprint_invention_products', product['typeID'],
                                        self.get_bpc_icon(cursor, product['typeID']),
                                        'quantity, probability',
                                        (product.get("quantity", -1), product.get("probability", 0)))
                        for skill in inv.get('skills', []):
                            if "typeID" in skill:
                                add_row('blueprint_invention_skills', skill['typeID'],
                                        self.get_type_icon(cursor, skill['typeID']),
                                        'level', (skill.get("level", -1),))
                
                except Exception as e:
                    print(f"[!] 处理蓝图 {blueprint_id} 时出错: {str(e)}")
                    continue

            print(f"[+] 已处理 {len(blueprints_data)} 个蓝图数据")
            
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
        db_path = get_db_path(self.config)
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 处理数据
            self.process_blueprints_to_db(blueprints_data, cursor)
            
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
        
        return self.process_blueprints_for_language('en')


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

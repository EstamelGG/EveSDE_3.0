#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宇宙名称处理器模块
处理EVE宇宙中的星域、星座、星系名称并存储到数据库
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import wide_texts, names_row, names_ddl, name_cols_sql
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any
import evesde.processors.jsonl_loader as jsonl_loader


class UniverseNamesProcessor:
    """EVE宇宙名称处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.regions_data = {}
        self.constellations_data = {}
        self.solar_systems_data = {}

    def load_universe_names_data(self):
        print("[+] 加载宇宙名称数据...")

        regions_file = self.sde_input_path / "mapRegions.jsonl"
        regions_list = jsonl_loader.load_jsonl(str(regions_file))
        self.regions_data = {item['_key']: item for item in regions_list}
        print(f"[+] 加载了 {len(self.regions_data)} 个星域")

        constellations_file = self.sde_input_path / "mapConstellations.jsonl"
        constellations_list = jsonl_loader.load_jsonl(str(constellations_file))
        self.constellations_data = {item['_key']: item for item in constellations_list}
        print(f"[+] 加载了 {len(self.constellations_data)} 个星座")

        solar_systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        solar_systems_list = jsonl_loader.load_jsonl(str(solar_systems_file))
        self.solar_systems_data = {item['_key']: item for item in solar_systems_list}
        print(f"[+] 加载了 {len(self.solar_systems_data)} 个星系")

    def create_tables(self, cursor: sqlite3.Cursor):
        print("[+] 创建宇宙名称表...")
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS regions (
                regionID INTEGER NOT NULL PRIMARY KEY,
                {names_ddl()}
            )
        ''')
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS constellations (
                constellationID INTEGER NOT NULL PRIMARY KEY,
                {names_ddl()}
            )
        ''')
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS solarsystems (
                solarSystemID INTEGER NOT NULL PRIMARY KEY,
                {names_ddl()},
                security_status REAL
            )
        ''')
        print("[+] 宇宙名称表创建完成")

    def process_universe_names_to_db(self, cursor: sqlite3.Cursor):
        print("[+] 开始处理宇宙名称数据...")
        start_time = time.time()

        self.create_tables(cursor)
        cursor.execute('DELETE FROM regions')
        cursor.execute('DELETE FROM constellations')
        cursor.execute('DELETE FROM solarsystems')

        name_cols = name_cols_sql()
        regions_sql = f'''
            INSERT OR REPLACE INTO regions (regionID, {name_cols})
            VALUES (?, {", ".join(["?"] * 8)})
        '''
        constellations_sql = f'''
            INSERT OR REPLACE INTO constellations (constellationID, {name_cols})
            VALUES (?, {", ".join(["?"] * 8)})
        '''
        systems_sql = f'''
            INSERT OR REPLACE INTO solarsystems (solarSystemID, {name_cols}, security_status)
            VALUES (?, {", ".join(["?"] * 8)}, ?)
        '''

        regions_count = 0
        for region_id, region_data in self.regions_data.items():
            names = wide_texts(region_data.get('name'))
            if not names.get('en'):
                continue
            cursor.execute(regions_sql, (region_id, *names_row(names)))
            regions_count += 1

        constellations_count = 0
        for const_id, const_data in self.constellations_data.items():
            names = wide_texts(const_data.get('name'))
            if not names.get('en'):
                continue
            cursor.execute(constellations_sql, (const_id, *names_row(names)))
            constellations_count += 1

        systems_count = 0
        for sys_id, sys_data in self.solar_systems_data.items():
            names = wide_texts(sys_data.get('name'))
            if not names.get('en'):
                continue
            security_status = sys_data.get('securityStatus', 0.0)
            cursor.execute(systems_sql, (sys_id, *names_row(names), security_status))
            systems_count += 1

        end_time = time.time()
        print(f"[+] 宇宙名称数据处理完成:")
        print(f"    - 星域: {regions_count} 个")
        print(f"    - 星座: {constellations_count} 个")
        print(f"    - 星系: {systems_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")

    def update_all_databases(self, config):
        self.load_universe_names_data()
        db_file = get_db_path(config)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n[+] 处理数据库: {db_file}")
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            self.process_universe_names_to_db(cursor)
            conn.commit()
            conn.close()
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")


def main(config=None):
    print("[+] 宇宙名称处理器启动")
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    processor = UniverseNamesProcessor(config)
    processor.update_all_databases(config)
    print("\n[+] 宇宙名称处理器完成")


if __name__ == "__main__":
    main()

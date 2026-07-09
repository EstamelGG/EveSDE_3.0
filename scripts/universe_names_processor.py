#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宇宙名称处理器模块
处理EVE宇宙中的星域、星座、星系名称并存储到数据库
基于SDE的JSONL文件创建多语言名称数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


# 支持的语言列表
LANGUAGES = ['de', 'en', 'es', 'fr', 'ja', 'ko', 'ru', 'zh']


class UniverseNamesProcessor:
    """EVE宇宙名称处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化宇宙名称处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.regions_data = {}
        self.constellations_data = {}
        self.solar_systems_data = {}
    
    def load_universe_names_data(self):
        """加载宇宙名称数据"""
        print("[+] 加载宇宙名称数据...")
        
        # 加载星域数据
        regions_file = self.sde_input_path / "mapRegions.jsonl"
        regions_list = jsonl_loader.load_jsonl(str(regions_file))
        self.regions_data = {item['_key']: item for item in regions_list}
        print(f"[+] 加载了 {len(self.regions_data)} 个星域")
        
        # 加载星座数据
        constellations_file = self.sde_input_path / "mapConstellations.jsonl"
        constellations_list = jsonl_loader.load_jsonl(str(constellations_file))
        self.constellations_data = {item['_key']: item for item in constellations_list}
        print(f"[+] 加载了 {len(self.constellations_data)} 个星座")
        
        # 加载星系数据
        solar_systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        solar_systems_list = jsonl_loader.load_jsonl(str(solar_systems_file))
        self.solar_systems_data = {item['_key']: item for item in solar_systems_list}
        print(f"[+] 加载了 {len(self.solar_systems_data)} 个星系")
    
    def create_tables(self, cursor: sqlite3.Cursor):
        """创建所需的表"""
        print("[+] 创建宇宙名称表...")
        
        # 构建语言列的SQL片段 - regions表
        region_lang_columns = ', '.join([f"regionName_{lang} TEXT" for lang in LANGUAGES])
        
        # 构建语言列的SQL片段 - constellations表
        constellation_lang_columns = ', '.join([f"constellationName_{lang} TEXT" for lang in LANGUAGES])
        
        # 构建语言列的SQL片段 - solarsystems表
        system_lang_columns = ', '.join([f"solarSystemName_{lang} TEXT" for lang in LANGUAGES])
        
        # 创建星域表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS regions (
                regionID INTEGER NOT NULL PRIMARY KEY,
                regionName TEXT,  -- 英文名称
                {region_lang_columns}
            )
        ''')
        
        # 创建星座表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS constellations (
                constellationID INTEGER NOT NULL PRIMARY KEY,
                constellationName TEXT,  -- 英文名称
                {constellation_lang_columns}
            )
        ''')
        
        # 创建恒星系表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS solarsystems (
                solarSystemID INTEGER NOT NULL PRIMARY KEY,
                solarSystemName TEXT,  -- 英文名称
                {system_lang_columns},
                security_status REAL
            )
        ''')
        
        print("[+] 宇宙名称表创建完成")
    
    def process_universe_names_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理宇宙名称数据并插入到数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理宇宙名称数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_tables(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM regions')
        cursor.execute('DELETE FROM constellations')
        cursor.execute('DELETE FROM solarsystems')
        
        # 准备SQL语句
        regions_sql = f'''
            INSERT OR REPLACE INTO regions (regionID, regionName, {', '.join([f'regionName_{lang}' for lang in LANGUAGES])})
            VALUES (?, ?, {', '.join(['?' for _ in LANGUAGES])})
        '''
        
        constellations_sql = f'''
            INSERT OR REPLACE INTO constellations (constellationID, constellationName, {', '.join([f'constellationName_{lang}' for lang in LANGUAGES])})
            VALUES (?, ?, {', '.join(['?' for _ in LANGUAGES])})
        '''
        
        solarsystems_sql = f'''
            INSERT OR REPLACE INTO solarsystems (solarSystemID, solarSystemName, {', '.join([f'solarSystemName_{lang}' for lang in LANGUAGES])}, security_status)
            VALUES (?, ?, {', '.join(['?' for _ in LANGUAGES])}, ?)
        '''
        
        # 处理星域数据
        regions_count = 0
        for region_id, region_data in self.regions_data.items():
            region_names = region_data.get('name', {})
            if not region_names:
                continue
            
            region_values = [
                region_id,
                region_names.get(lang, region_names.get('en', ''))  # 使用指定语言的名称，如果没有则使用英文
            ]
            
            # 添加所有语言的名称
            for lang_code in LANGUAGES:
                region_values.append(region_names.get(lang_code, ''))
            
            cursor.execute(regions_sql, region_values)
            regions_count += 1
        
        # 处理星座数据
        constellations_count = 0
        for const_id, const_data in self.constellations_data.items():
            const_names = const_data.get('name', {})
            if not const_names:
                continue
            
            const_values = [
                const_id,
                const_names.get(lang, const_names.get('en', ''))  # 使用指定语言的名称，如果没有则使用英文
            ]
            
            # 添加所有语言的名称
            for lang_code in LANGUAGES:
                const_values.append(const_names.get(lang_code, ''))
            
            cursor.execute(constellations_sql, const_values)
            constellations_count += 1
        
        # 处理星系数据
        systems_count = 0
        for sys_id, sys_data in self.solar_systems_data.items():
            sys_names = sys_data.get('name', {})
            if not sys_names:
                continue
            
            sys_values = [
                sys_id,
                sys_names.get(lang, sys_names.get('en', ''))  # 使用指定语言的名称，如果没有则使用英文
            ]
            
            # 添加所有语言的名称
            for lang_code in LANGUAGES:
                sys_values.append(sys_names.get(lang_code, ''))
            
            # 添加安全等级
            security_status = sys_data.get('securityStatus', 0.0)
            sys_values.append(security_status)
            
            cursor.execute(solarsystems_sql, sys_values)
            systems_count += 1
        
        end_time = time.time()
        print(f"[+] 宇宙名称数据处理完成:")
        print(f"    - 星域: {regions_count} 个")
        print(f"    - 星座: {constellations_count} 个")
        print(f"    - 星系: {systems_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载宇宙名称数据
        self.load_universe_names_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理宇宙名称数据
                self.process_universe_names_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 宇宙名称处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = UniverseNamesProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 宇宙名称处理器完成")


if __name__ == "__main__":
    main()

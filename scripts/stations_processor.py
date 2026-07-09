#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间站处理器模块
处理EVE空间站数据并存储到数据库
"""

import json
import sqlite3
import time
import roman
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class StationsProcessor:
    """EVE空间站处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化空间站处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.npc_stations_data = {}
        self.station_operations_data = {}
        self.solar_systems_data = {}
        self.npc_corporations_data = {}
    
    def load_stations_data(self):
        """加载空间站相关数据"""
        print("[+] 加载空间站数据...")
        
        # 加载NPC空间站数据
        npc_stations_file = self.sde_input_path / "npcStations.jsonl"
        if npc_stations_file.exists():
            npc_stations_list = jsonl_loader.load_jsonl(str(npc_stations_file))
            self.npc_stations_data = {item['_key']: item for item in npc_stations_list}
            print(f"[+] 加载了 {len(self.npc_stations_data)} 个NPC空间站")
        
        # 加载空间站操作数据
        station_operations_file = self.sde_input_path / "stationOperations.jsonl"
        if station_operations_file.exists():
            operations_list = jsonl_loader.load_jsonl(str(station_operations_file))
            self.station_operations_data = {item['_key']: item for item in operations_list}
            print(f"[+] 加载了 {len(self.station_operations_data)} 个空间站操作")
        
        # 加载星系数据
        solar_systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        if solar_systems_file.exists():
            systems_list = jsonl_loader.load_jsonl(str(solar_systems_file))
            self.solar_systems_data = {item['_key']: item for item in systems_list}
            print(f"[+] 加载了 {len(self.solar_systems_data)} 个星系")
        
        # 加载NPC军团数据
        npc_corporations_file = self.sde_input_path / "npcCorporations.jsonl"
        if npc_corporations_file.exists():
            corporations_list = jsonl_loader.load_jsonl(str(npc_corporations_file))
            self.npc_corporations_data = {item['_key']: item for item in corporations_list}
            print(f"[+] 加载了 {len(self.npc_corporations_data)} 个NPC军团")
    
    def int_to_roman(self, num: int) -> str:
        """将整数转换为罗马数字"""
        if num <= 0:
            return str(num)
        
        try:
            return roman.toRoman(num)
        except Exception as e:
            print(f"[x] 罗马数字转换失败 {num}: {e}")
            return str(num)
    
    def generate_station_name(self, station_data: Dict[str, Any], lang: str = 'en') -> str:
        """
        生成空间站名称
        格式: 星系名 - celestialIndex(转罗马数字) - 月球{orbitIndex} - ownerID对应的军团名称 {空格} operationID对应的名称
        """
        try:
            # 获取基本信息
            solar_system_id = station_data.get('solarSystemID', 0)
            celestial_index = station_data.get('celestialIndex', 0)
            orbit_index = station_data.get('orbitIndex', 0)
            owner_id = station_data.get('ownerID', 0)
            operation_id = station_data.get('operationID', 0)
            use_operation_name = station_data.get('useOperationName', False)
            
            # 获取星系名称
            system_name = ""
            if solar_system_id in self.solar_systems_data:
                system_names = self.solar_systems_data[solar_system_id].get('name', {})
                system_name = system_names.get(lang, system_names.get('en', ''))
            
            # 转换celestialIndex为罗马数字
            celestial_roman = self.int_to_roman(celestial_index)
            
            # 获取军团名称
            corp_name = ""
            if owner_id in self.npc_corporations_data:
                corp_names = self.npc_corporations_data[owner_id].get('name', {})
                corp_name = corp_names.get(lang, corp_names.get('en', ''))
            
            # 获取操作名称
            operation_name = ""
            if use_operation_name and operation_id in self.station_operations_data:
                operation_names = self.station_operations_data[operation_id].get('operationName', {})
                operation_name = operation_names.get(lang, operation_names.get('en', ''))
            
            # 组合名称
            if system_name and corp_name:
                # 第一部分：星系名 + 天体罗马数字（如果存在且不为0）
                if celestial_index and celestial_index > 0:
                    part1 = f"{system_name} {celestial_roman}"
                else:
                    part1 = system_name
                
                # 第二部分：卫星部分（如果有轨道索引）
                if orbit_index > 0:
                    moon_text = "卫星" if lang == 'zh' else "Moon"
                    part1 = f"{part1} - {moon_text} {orbit_index}"
                
                # 第三部分：军团名称和操作名称
                corp_operation = corp_name
                if operation_name:
                    corp_operation = f"{corp_name} {operation_name}"
                
                return f"{part1} - {corp_operation}"
            else:
                # 如果缺少必要信息，返回基本格式
                return f"Station {station_data.get('_key', 'Unknown')}"
                
        except Exception as e:
            print(f"[x] 生成空间站名称失败: {e}")
            return f"Station {station_data.get('_key', 'Unknown')}"
    
    def create_stations_tables(self, cursor: sqlite3.Cursor):
        """创建空间站相关表"""
        
        # 空间站表（简化版，只保留必要字段）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                stationID INTEGER NOT NULL PRIMARY KEY,
                stationTypeID INTEGER,
                stationName TEXT,
                regionID INTEGER,
                solarSystemID INTEGER,
                security REAL
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stations_solarSystemID ON stations(solarSystemID)')
    
    def process_npc_stations_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理NPC空间站数据并插入数据库"""
        print(f"[+] 开始处理NPC空间站数据 (语言: {lang})...")
        
        # 清空现有数据
        cursor.execute('DELETE FROM stations')
        
        stations_batch = []
        batch_size = 1000
        
        for station_id, station_data in self.npc_stations_data.items():
            # 获取基本信息
            solar_system_id = station_data.get('solarSystemID', 0)
            station_type_id = station_data.get('typeID', 0)
            
            # 生成空间站名称
            station_name = self.generate_station_name(station_data, lang)
            
            # 获取regionID和security（从星系数据中）
            region_id = 0
            security = 0.0
            if solar_system_id in self.solar_systems_data:
                system_data = self.solar_systems_data[solar_system_id]
                region_id = system_data.get('regionID', 0)
                security = system_data.get('securityStatus', 0.0)
            
            stations_batch.append((
                station_id, station_type_id, station_name,
                region_id, solar_system_id, security
            ))
            
            # 批量插入
            if len(stations_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO stations (
                        stationID, stationTypeID, stationName,
                        regionID, solarSystemID, security
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', stations_batch)
                stations_batch = []
        
        # 处理剩余数据
        if stations_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO stations (
                    stationID, stationTypeID, stationName,
                    regionID, solarSystemID, security
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', stations_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM stations')
        stations_count = cursor.fetchone()[0]
        print(f"[+] NPC空间站数据处理完成: {stations_count} 个")
    
    
    
    def process_stations_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理所有空间站数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理空间站数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_stations_tables(cursor)
        
        # 处理空间站数据
        self.process_npc_stations_to_db(cursor, lang)
        
        end_time = time.time()
        print(f"[+] 空间站数据处理完成，耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载空间站数据
        self.load_stations_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理空间站数据
                self.process_stations_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 空间站处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = StationsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 空间站处理器完成")


if __name__ == "__main__":
    main()

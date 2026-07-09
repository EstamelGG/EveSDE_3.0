#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宇宙数据处理器模块
处理EVE宇宙数据并存储到数据库，包括星域、星座、星系、行星等信息
"""

import json
import sqlite3
import time
import re
from pathlib import Path
from utils.http_client import get
from typing import List, Dict, Any, Set
from scripts.jsonl_loader import load_jsonl


# 行星类型映射
PLANETARY_TYPE_MAPPING = {
    "temperate": 11,
    "barren": 2016,
    "oceanic": 2014,
    "ice": 12,
    "gas": 13,
    "lava": 2015,
    "storm": 2017,
    "plasma": 2063
}


class UniverseProcessor:
    """EVE宇宙数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化宇宙数据处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.regions_data = {}
        self.constellations_data = {}
        self.solar_systems_data = {}
        self.planets_data = {}
        self.stations_data = {}
        self.stars_data = {}  # 添加恒星数据缓存
        self.jove_systems = set()
        
        # 缓存目录
        self.cache_dir = self.project_root / "cache"
        self.cache_dir.mkdir(exist_ok=True)
    
    def fetch_jove_systems(self) -> Set[str]:
        """从网络获取Jove星系列表，使用缓存"""
        jo_url = "https://jambeeno.com/jo.txt"
        local_file = self.cache_dir / "jo.txt"
        
        # 检查缓存文件是否存在
        if not local_file.exists():
            try:
                print(f"[+] 从网络获取Jove星系列表: {jo_url}")
                response = get(jo_url, timeout=30, verify=False)
                
                # 保存到缓存目录
                with open(local_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"[+] Jove星系列表已缓存到: {local_file}")
                
            except Exception as e:
                print(f"[!] 从网络获取Jove星系列表失败: {e}")
                return set()
        else:
            print(f"[+] 使用缓存的Jove星系列表: {local_file}")
        
        # 从缓存文件读取
        jove_systems = set()
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and line_num > 1:  # 跳过标题行
                        parts = line.split(',')
                        if len(parts) >= 2:
                            system_name = parts[1].strip()
                            jove_systems.add(system_name)
            
            print(f"[+] 从缓存文件读取了 {len(jove_systems)} 个Jove星系")
            
        except Exception as e:
            print(f"[!] 读取Jove星系缓存文件失败: {e}")
        
        return jove_systems
    
    def load_universe_data(self):
        """加载宇宙数据"""
        print("[+] 加载宇宙数据...")
        
        # 加载星域数据
        regions_file = self.sde_input_path / "mapRegions.jsonl"
        regions_list = load_jsonl(str(regions_file))
        self.regions_data = {item['_key']: item for item in regions_list}
        print(f"[+] 加载了 {len(self.regions_data)} 个星域")
        
        # 加载星座数据
        constellations_file = self.sde_input_path / "mapConstellations.jsonl"
        constellations_list = load_jsonl(str(constellations_file))
        self.constellations_data = {item['_key']: item for item in constellations_list}
        print(f"[+] 加载了 {len(self.constellations_data)} 个星座")
        
        # 加载星系数据
        solar_systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        solar_systems_list = load_jsonl(str(solar_systems_file))
        self.solar_systems_data = {item['_key']: item for item in solar_systems_list}
        print(f"[+] 加载了 {len(self.solar_systems_data)} 个星系")
        
        # 加载行星数据
        planets_file = self.sde_input_path / "mapPlanets.jsonl"
        planets_list = load_jsonl(str(planets_file))
        
        # 按星系组织行星数据
        for planet in planets_list:
            system_id = planet.get('solarSystemID')
            if system_id:
                if system_id not in self.planets_data:
                    self.planets_data[system_id] = []
                self.planets_data[system_id].append(planet)
        
        print(f"[+] 加载了 {len(planets_list)} 个行星，分布在 {len(self.planets_data)} 个星系")
        
        # 加载空间站数据
        stations_file = self.sde_input_path / "npcStations.jsonl"
        stations_list = load_jsonl(str(stations_file))
        
        # 按星系组织空间站数据
        for station in stations_list:
            system_id = station.get('solarSystemID')
            if system_id:
                if system_id not in self.stations_data:
                    self.stations_data[system_id] = []
                self.stations_data[system_id].append(station)
        
        print(f"[+] 加载了 {len(stations_list)} 个空间站，分布在 {len(self.stations_data)} 个星系")
        
        # 加载恒星数据
        stars_file = self.sde_input_path / "mapStars.jsonl"
        stars_list = load_jsonl(str(stars_file))
        self.stars_data = {item['_key']: item for item in stars_list}
        print(f"[+] 加载了 {len(self.stars_data)} 个恒星")
        
        # 获取Jove星系列表
        self.jove_systems = self.fetch_jove_systems()
    
    def create_universe_table(self, cursor: sqlite3.Cursor):
        """创建universe表"""
        print("[+] 创建universe表...")
        
        # 构建表结构
        table_schema = '''
            CREATE TABLE IF NOT EXISTS universe (
                region_id INTEGER NOT NULL,
                constellation_id INTEGER NOT NULL,
                solarsystem_id INTEGER NOT NULL,
                system_security REAL,
                system_type INTEGER,
                x REAL,
                y REAL,
                z REAL,
                hasStation BOOLEAN NOT NULL DEFAULT 0,
                hasJumpGate BOOLEAN NOT NULL DEFAULT 0,
                isJSpace BOOLEAN NOT NULL DEFAULT 0,
                jove BOOLEAN NOT NULL DEFAULT 0
        '''
        
        # 添加行星类型列
        for planet_name in PLANETARY_TYPE_MAPPING.keys():
            table_schema += f',\n                {planet_name} INTEGER NOT NULL DEFAULT 0'
        
        # 添加主键约束
        table_schema += ''',
                PRIMARY KEY (region_id, constellation_id, solarsystem_id)
            )
        '''
        
        cursor.execute(table_schema)
        print(f"[+] 创建了包含 {len(PLANETARY_TYPE_MAPPING)} 种行星类型的universe表")
    
    def count_planets_by_type(self, system_id: int) -> Dict[str, int]:
        """统计星系中各类型行星的数量"""
        planet_counts = {name: 0 for name in PLANETARY_TYPE_MAPPING.keys()}
        
        if system_id in self.planets_data:
            # 创建类型ID到名称的反向映射
            type_to_name = {type_id: name for name, type_id in PLANETARY_TYPE_MAPPING.items()}
            
            for planet in self.planets_data[system_id]:
                planet_type_id = planet.get('typeID')
                if planet_type_id in type_to_name:
                    planet_name = type_to_name[planet_type_id]
                    planet_counts[planet_name] += 1
        
        return planet_counts
    
    def process_universe_data_to_db(self, cursor: sqlite3.Cursor):
        """处理宇宙数据并插入数据库"""
        print("[+] 开始处理宇宙数据...")
        start_time = time.time()
        
        # 创建表
        self.create_universe_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM universe')
        
        # JSpace正则表达式
        jspace_pattern = re.compile(r'^J\d+$')
        
        universe_records = []
        processed_count = 0
        
        # 遍历所有星系
        for system_id, system_data in self.solar_systems_data.items():
            constellation_id = system_data.get('constellationID')
            if not constellation_id:
                continue
            
            # 获取星座信息
            constellation_data = self.constellations_data.get(constellation_id)
            if not constellation_data:
                continue
            
            region_id = constellation_data.get('regionID')
            if not region_id:
                continue
            
            # 获取星系基本信息
            security_status = system_data.get('securityStatus', 0.0)
            star_id = system_data.get('starID')
            
            # 获取恒星类型ID
            system_type = 6  # 默认恒星类型
            if star_id and star_id in self.stars_data:
                star_data = self.stars_data[star_id]
                system_type = star_data.get('typeID', 6)
            
            # 获取坐标
            position = system_data.get('position', {})
            x = position.get('x', 0.0)
            y = position.get('y', 0.0)
            z = position.get('z', 0.0)
            
            # 检查是否有空间站
            has_station = system_id in self.stations_data
            
            # 检查是否有星门
            stargates = system_data.get('stargateIDs', [])
            has_stargates = len(stargates) > 0 if isinstance(stargates, list) else False
            
            # 获取星系名称（英文）
            system_name = ""
            if 'name' in system_data and isinstance(system_data['name'], dict):
                system_name = system_data['name'].get('en', '')
            
            # 检查是否为JSpace
            is_jspace = bool(jspace_pattern.match(system_name) or system_name == "J1226-0") and not has_stargates
            
            # 检查是否为Jove星系
            is_jove = system_name in self.jove_systems
            
            # 统计行星类型
            planet_counts = self.count_planets_by_type(system_id)
            
            # 构建数据记录
            record = [
                region_id,
                constellation_id,
                system_id,
                float(security_status),
                system_type,  # 使用恒星类型ID而不是恒星ID
                float(x),
                float(y),
                float(z),
                has_station,
                has_stargates,
                is_jspace,
                is_jove
            ]
            
            # 添加行星类型计数
            for planet_name in PLANETARY_TYPE_MAPPING.keys():
                record.append(planet_counts.get(planet_name, 0))
            
            universe_records.append(tuple(record))
            processed_count += 1
            
            if processed_count % 1000 == 0:
                print(f"\r[+] 处理进度: {processed_count}/{len(self.solar_systems_data)}", end='', flush=True)
        
        print(f"\n[+] 数据处理完成，共 {len(universe_records)} 条记录")
        
        # 批量插入数据
        if universe_records:
            # 构建SQL语句
            columns = [
                'region_id', 'constellation_id', 'solarsystem_id', 
                'system_security', 'system_type', 'x', 'y', 'z', 
                'hasStation', 'hasJumpGate', 'isJSpace', 'jove'
            ]
            
            # 添加行星类型列
            for planet_name in PLANETARY_TYPE_MAPPING.keys():
                columns.append(planet_name)
            
            placeholders = ', '.join(['?' for _ in range(len(columns))])
            columns_str = ', '.join(columns)
            sql = f'INSERT OR REPLACE INTO universe ({columns_str}) VALUES ({placeholders})'
            
            # 批量插入
            batch_size = 1000
            for i in range(0, len(universe_records), batch_size):
                batch = universe_records[i:i + batch_size]
                cursor.executemany(sql, batch)
                print(f"\r[+] 插入进度: {min(i + batch_size, len(universe_records))}/{len(universe_records)}", end='', flush=True)
        
        print(f"\n[+] 数据插入完成")
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM universe')
        total_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM universe WHERE hasStation = 1')
        station_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM universe WHERE isJSpace = 1')
        jspace_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM universe WHERE jove = 1')
        jove_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"\n[+] 宇宙数据处理完成:")
        print(f"    - 总星系数: {total_count}")
        print(f"    - 有空间站: {station_count}")
        print(f"    - JSpace星系: {jspace_count}")
        print(f"    - Jove星系: {jove_count}")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载宇宙数据
        self.load_universe_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理宇宙数据
                self.process_universe_data_to_db(cursor)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 宇宙数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = UniverseProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 宇宙数据处理器完成")


if __name__ == "__main__":
    main()

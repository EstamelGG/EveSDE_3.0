#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天体数据处理器
从 mapPlanets.jsonl 和 mapMoons.jsonl 提取天体定位参数，写入 celestials 表。

名称不在构建期生成，由客户端运行时通过 JOIN solarsystems + 罗马数字转换拼接：
- 行星: {system_name} {roman(celestialIndex)}
- 月球: {system_name} {roman(celestialIndex)} - {Moon/卫星} {orbitIndex}

表结构:
- itemID: 天体 ID（行星或月球，主键）
- solarSystemID: 所在星系 ID（JOIN solarsystems 取多语星系名）
- celestialIndex: 天体索引（客户端转罗马数字）
- orbitIndex: 轨道索引（NULL = 行星，非 NULL = 月球）
"""

from utils.single_db import get_db_path
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any


class CelestialsProcessor:
    """天体数据处理器：仅存定位参数，名称由客户端运行时生成"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.planets_data: Dict[Any, Dict[str, Any]] = {}
        self.moons_data: Dict[Any, Dict[str, Any]] = {}

    def read_jsonl(self, filename: str) -> Dict[Any, Dict[str, Any]]:
        """读取 JSONL 文件并按 _key 建立索引"""
        jsonl_file = self.sde_jsonl_path / filename
        if not jsonl_file.exists():
            print(f"[x] 找不到文件: {jsonl_file}")
            return {}

        print(f"[+] 读取 {jsonl_file}")
        data: Dict[Any, Dict[str, Any]] = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        data[item['_key']] = item
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"[!] {filename} 第{line_num}行: {e}")
                        continue
            print(f"[+] 成功读取 {len(data)} 个记录（{filename}）")
            return data
        except Exception as e:
            print(f"[x] 读取 {filename} 时出错: {e}")
            return {}

    def create_celestials_table(self, cursor: sqlite3.Cursor):
        """创建 celestials 表，并清理旧的 celestialNames 表（已被 celestials 取代）"""
        cursor.execute('DROP TABLE IF EXISTS celestialNames')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS celestials (
                itemID INTEGER NOT NULL PRIMARY KEY,
                solarSystemID INTEGER NOT NULL,
                celestialIndex INTEGER NOT NULL,
                orbitIndex INTEGER
            )
        ''')
        print("[+] 创建 celestials 表（已清理旧 celestialNames 表）")

    def process_to_db(self, cursor: sqlite3.Cursor):
        """写入天体定位参数"""
        self.create_celestials_table(cursor)
        cursor.execute('DELETE FROM celestials')

        insert_sql = (
            "INSERT OR REPLACE INTO celestials "
            "(itemID, solarSystemID, celestialIndex, orbitIndex) VALUES (?, ?, ?, ?)"
        )
        batch = []
        batch_size = 1000

        # 行星：orbitIndex = NULL
        for planet_id, planet_data in self.planets_data.items():
            batch.append((
                planet_id,
                planet_data.get('solarSystemID', 0),
                planet_data.get('celestialIndex', 0),
                None,
            ))
            if len(batch) >= batch_size:
                cursor.executemany(insert_sql, batch)
                batch = []
        print(f"[+] 已处理 {len(self.planets_data)} 个行星")

        # 月球：orbitIndex 有值
        for moon_id, moon_data in self.moons_data.items():
            batch.append((
                moon_id,
                moon_data.get('solarSystemID', 0),
                moon_data.get('celestialIndex', 0),
                moon_data.get('orbitIndex'),
            ))
            if len(batch) >= batch_size:
                cursor.executemany(insert_sql, batch)
                batch = []
        print(f"[+] 已处理 {len(self.moons_data)} 个月球")

        if batch:
            cursor.executemany(insert_sql, batch)

        total = cursor.execute('SELECT COUNT(*) FROM celestials').fetchone()[0]
        planet_count = cursor.execute(
            'SELECT COUNT(*) FROM celestials WHERE orbitIndex IS NULL'
        ).fetchone()[0]
        moon_count = total - planet_count
        print(f"[+] celestials 处理完成: {total} 个天体（行星 {planet_count}, 月球 {moon_count}）")

    def process(self) -> bool:
        print("[+] 开始处理天体数据")
        self.planets_data = self.read_jsonl("mapPlanets.jsonl")
        self.moons_data = self.read_jsonl("mapMoons.jsonl")
        if not self.planets_data or not self.moons_data:
            print("[x] 无法加载行星/月球数据")
            return False

        db_path = get_db_path(self.config)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            self.process_to_db(cursor)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[x] 处理天体数据时出错: {e}")
            return False


def main(config=None):
    print("[+] 天体数据处理器启动")
    if config is None:
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    processor = CelestialsProcessor(config)
    processor.process()
    print("\n[+] 天体数据处理器完成")


if __name__ == "__main__":
    main()

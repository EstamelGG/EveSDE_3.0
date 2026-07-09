#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天体名称数据处理器模块
用于处理行星和月球名称数据并写入数据库

功能: 从mapPlanets.jsonl和mapMoons.jsonl获取数据，生成天体名称
命名规则:
- 行星: 星系名称 + 罗马数字 (如: Sasta VII)
- 月球: 星系名称 + 罗马数字 + Moon + 轨道索引 (如: Sasta VII - Moon 6)
"""

import json
import sqlite3
import roman
from pathlib import Path
from typing import Dict, Any, List, Optional


class CelestialNamesProcessor:
    """天体名称数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化天体名称处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        
        # 缓存数据
        self.planets_data = {}
        self.moons_data = {}
        self.solar_systems_data = {}
    
    def int_to_roman(self, num: int) -> str:
        """将整数转换为罗马数字"""
        if num <= 0:
            return str(num)
        
        try:
            return roman.toRoman(num)
        except Exception as e:
            print(f"[!] 罗马数字转换失败 {num}: {e}")
            return str(num)
    
    def read_planets_jsonl(self) -> Dict[str, Any]:
        """读取mapPlanets JSONL文件"""
        jsonl_file = self.sde_jsonl_path / "mapPlanets.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到mapPlanets JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取mapPlanets JSONL文件: {jsonl_file}")
        
        planets_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        planet_id = data['_key']
                        planets_data[planet_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(planets_data)} 个行星记录")
            return planets_data
            
        except Exception as e:
            print(f"[x] 读取mapPlanets JSONL文件时出错: {e}")
            return {}
    
    def read_moons_jsonl(self) -> Dict[str, Any]:
        """读取mapMoons JSONL文件"""
        jsonl_file = self.sde_jsonl_path / "mapMoons.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到mapMoons JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取mapMoons JSONL文件: {jsonl_file}")
        
        moons_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        moon_id = data['_key']
                        moons_data[moon_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(moons_data)} 个月球记录")
            return moons_data
            
        except Exception as e:
            print(f"[x] 读取mapMoons JSONL文件时出错: {e}")
            return {}
    
    def read_solar_systems_jsonl(self) -> Dict[str, Any]:
        """读取mapSolarSystems JSONL文件"""
        jsonl_file = self.sde_jsonl_path / "mapSolarSystems.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到mapSolarSystems JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取mapSolarSystems JSONL文件: {jsonl_file}")
        
        systems_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        system_id = data['_key']
                        systems_data[system_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(systems_data)} 个星系记录")
            return systems_data
            
        except Exception as e:
            print(f"[x] 读取mapSolarSystems JSONL文件时出错: {e}")
            return {}
    
    def get_system_name(self, system_id: int, lang: str = 'en') -> str:
        """获取星系名称"""
        if system_id in self.solar_systems_data:
            system_data = self.solar_systems_data[system_id]
            system_names = system_data.get('name', {})
            return system_names.get(lang, system_names.get('en', f'System_{system_id}'))
        return f'System_{system_id}'
    
    def generate_planet_name(self, planet_data: Dict[str, Any], lang: str = 'en') -> str:
        """生成行星名称"""
        try:
            solar_system_id = planet_data.get('solarSystemID', 0)
            celestial_index = planet_data.get('celestialIndex', 0)
            
            system_name = self.get_system_name(solar_system_id, lang)
            celestial_roman = self.int_to_roman(celestial_index)
            
            return f"{system_name} {celestial_roman}"
            
        except Exception as e:
            print(f"[!] 生成行星名称失败: {e}")
            return f"Planet_{planet_data.get('_key', 'Unknown')}"
    
    def generate_moon_name(self, moon_data: Dict[str, Any], lang: str = 'en') -> str:
        """生成月球名称"""
        try:
            solar_system_id = moon_data.get('solarSystemID', 0)
            celestial_index = moon_data.get('celestialIndex', 0)
            orbit_index = moon_data.get('orbitIndex', 0)
            
            system_name = self.get_system_name(solar_system_id, lang)
            celestial_roman = self.int_to_roman(celestial_index)
            
            # 根据语言选择"Moon"的翻译
            moon_text = "卫星" if lang == 'zh' else "Moon"
            
            return f"{system_name} {celestial_roman} - {moon_text} {orbit_index}"
            
        except Exception as e:
            print(f"[!] 生成月球名称失败: {e}")
            return f"Moon_{moon_data.get('_key', 'Unknown')}"
    
    def create_celestial_names_table(self, cursor: sqlite3.Cursor):
        """创建天体名称表"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS celestialNames (
            itemID INTEGER NOT NULL PRIMARY KEY,
            itemName TEXT
        )
        ''')
        print("[+] 创建celestialNames表")
    
    def process_celestial_names_to_db(self, cursor: sqlite3.Cursor, lang: str):
        """处理天体名称数据并写入数据库"""
        try:
            # 创建表
            self.create_celestial_names_table(cursor)
            
            # 清空现有数据
            cursor.execute('DELETE FROM celestialNames')
            
            # 处理行星数据
            planets_batch = []
            batch_size = 1000
            
            print(f"[+] 开始处理行星名称数据，语言: {lang}")
            for planet_id, planet_data in self.planets_data.items():
                planet_name = self.generate_planet_name(planet_data, lang)
                
                planets_batch.append((
                    planet_id, planet_name
                ))
                
                if len(planets_batch) >= batch_size:
                    cursor.executemany('''
                        INSERT OR REPLACE INTO celestialNames (
                            itemID, itemName
                        ) VALUES (?, ?)
                    ''', planets_batch)
                    planets_batch = []
            
            # 处理剩余行星数据
            if planets_batch:
                cursor.executemany('''
                    INSERT OR REPLACE INTO celestialNames (
                        itemID, itemName
                    ) VALUES (?, ?)
                ''', planets_batch)
            
            print(f"[+] 已处理 {len(self.planets_data)} 个行星名称")
            
            # 处理月球数据
            moons_batch = []
            print(f"[+] 开始处理月球名称数据，语言: {lang}")
            for moon_id, moon_data in self.moons_data.items():
                moon_name = self.generate_moon_name(moon_data, lang)
                
                moons_batch.append((
                    moon_id, moon_name
                ))
                
                if len(moons_batch) >= batch_size:
                    cursor.executemany('''
                        INSERT OR REPLACE INTO celestialNames (
                            itemID, itemName
                        ) VALUES (?, ?)
                    ''', moons_batch)
                    moons_batch = []
            
            # 处理剩余月球数据
            if moons_batch:
                cursor.executemany('''
                    INSERT OR REPLACE INTO celestialNames (
                        itemID, itemName
                    ) VALUES (?, ?)
                ''', moons_batch)
            
            print(f"[+] 已处理 {len(self.moons_data)} 个月球名称")
            
            # 统计信息
            cursor.execute('SELECT COUNT(*) FROM celestialNames')
            total_count = cursor.fetchone()[0]
            print(f"[+] 天体名称数据处理完成，总计: {total_count} 个，语言: {lang}")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_celestial_names_for_language(self, language: str) -> bool:
        """为指定语言处理天体名称数据"""
        print(f"[+] 开始处理天体名称数据，语言: {language}")
        
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
            self.process_celestial_names_to_db(cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] 天体名称数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理天体名称数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """为所有语言处理天体名称数据"""
        print("[+] 开始处理天体名称数据")
        
        # 加载数据
        self.planets_data = self.read_planets_jsonl()
        self.moons_data = self.read_moons_jsonl()
        self.solar_systems_data = self.read_solar_systems_jsonl()
        
        if not self.planets_data or not self.moons_data or not self.solar_systems_data:
            print("[x] 无法加载必要的数据文件")
            return False
        
        success_count = 0
        for language in self.languages:
            if self.process_celestial_names_for_language(language):
                success_count += 1
        
        print(f"[+] 天体名称数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 天体名称数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = CelestialNamesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 天体名称数据处理器完成")


if __name__ == "__main__":
    main()

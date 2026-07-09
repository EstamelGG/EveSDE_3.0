#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品材料产出数据处理器模块
用于处理typeMaterials数据并写入数据库

功能: 处理物品材料产出数据，创建typeMaterials表
完全按照old版本的逻辑实现，确保数据库结构一致
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


class TypeMaterialsProcessor:
    """物品材料产出数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化typeMaterials处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_type_materials_jsonl(self) -> Dict[str, Any]:
        """
        读取typeMaterials JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "typeMaterials.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到typeMaterials JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取typeMaterials JSONL文件: {jsonl_file}")
        
        type_materials_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为type_id
                        type_id = data['_key']
                        type_materials_data[type_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(type_materials_data)} 个typeMaterials记录")
            return type_materials_data
            
        except Exception as e:
            print(f"[x] 读取typeMaterials JSONL文件时出错: {e}")
            return {}
    
    def create_type_materials_table(self, cursor: sqlite3.Cursor):
        """
        创建typeMaterials表
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS typeMaterials (
            typeid INTEGER NOT NULL,
            categoryid INTEGER,
            process_size INTEGER,
            output_material INTEGER NOT NULL,
            output_material_categoryid INTEGER,
            output_material_groupid INTEGER,
            output_quantity INTEGER,
            output_material_name TEXT,
            output_material_icon TEXT,
            PRIMARY KEY (typeid, output_material)
        )
        ''')
        print("[+] 创建typeMaterials表")
    
    def create_type_randomized_materials_table(self, cursor: sqlite3.Cursor):
        """
        创建typeRandomizedMaterials表
        用于存储随机材料产出数据
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS typeRandomizedMaterials (
            type_id INTEGER NOT NULL,
            materialTypeID INTEGER NOT NULL,
            quantityMin INTEGER,
            quantityMax INTEGER,
            PRIMARY KEY (type_id, materialTypeID)
        )
        ''')
        print("[+] 创建typeRandomizedMaterials表")
    
    def get_type_info(self, cursor: sqlite3.Cursor, type_id: int, type_info_cache: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        """
        从缓存或数据库获取物品的所有相关信息
        """
        if type_id not in type_info_cache:
            cursor.execute('SELECT name, icon_filename, categoryID, groupID, process_size FROM types WHERE type_id = ?', (type_id,))
            result = cursor.fetchone()
            if result:
                type_info_cache[type_id] = {
                    'name': result[0],
                    'icon': result[1],
                    'categoryid': result[2],
                    'groupID': result[3],
                    'process_size': result[4]
                }
            else:
                type_info_cache[type_id] = {
                    'name': None,
                    'icon': None,
                    'categoryid': None,
                    'groupID': None,
                    'process_size': None
                }
        return type_info_cache[type_id]
    
    def process_type_materials_to_db(self, type_materials_data: Dict[str, Any], cursor: sqlite3.Cursor, lang: str):
        """
        处理typeMaterials数据并写入数据库
        完全按照old版本的逻辑
        """
        self.create_type_materials_table(cursor)
        self.create_type_randomized_materials_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM typeMaterials')
        cursor.execute('DELETE FROM typeRandomizedMaterials')
        
        # 创建物品信息缓存字典
        type_info_cache = {}
        
        # 用于存储批量插入的数据
        batch_data = []
        batch_randomized_data = []
        batch_size = 1000  # 每批处理的记录数
        
        # 处理每个物品的材料数据
        for type_id, type_data in type_materials_data.items():
            if 'materials' in type_data:
                # 获取物品的信息
                type_info = self.get_type_info(cursor, type_id, type_info_cache)
                category_id = type_info['categoryid']
                process_size = type_info['process_size']
                
                for material in type_data['materials']:
                    material_type_id = material['materialTypeID']
                    quantity = material['quantity']
                    material_info = self.get_type_info(cursor, material_type_id, type_info_cache)
                    
                    # 添加到批量数据
                    batch_data.append((
                        type_id, category_id, process_size, material_type_id, 
                        material_info['categoryid'], material_info['groupID'], 
                        quantity, material_info['name'], material_info['icon']
                    ))
                    
                    # 当达到批处理大小时执行插入
                    if len(batch_data) >= batch_size:
                        cursor.executemany('''
                            INSERT OR REPLACE INTO typeMaterials 
                            (typeid, categoryid, process_size, output_material, output_material_categoryid, 
                             output_material_groupid, output_quantity, output_material_name, output_material_icon) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', batch_data)
                        batch_data = []  # 清空批处理列表
            
            # 处理randomizedMaterials数据
            if 'randomizedMaterials' in type_data and isinstance(type_data['randomizedMaterials'], list):
                for randomized_material in type_data['randomizedMaterials']:
                    material_type_id = randomized_material.get('materialTypeID')
                    quantity_min = randomized_material.get('quantityMin')
                    quantity_max = randomized_material.get('quantityMax')
                    
                    if material_type_id is not None:
                        # 添加到批量数据
                        batch_randomized_data.append((
                            type_id, material_type_id, quantity_min, quantity_max
                        ))
                        
                        # 当达到批处理大小时执行插入
                        if len(batch_randomized_data) >= batch_size:
                            cursor.executemany('''
                                INSERT OR REPLACE INTO typeRandomizedMaterials 
                                (type_id, materialTypeID, quantityMin, quantityMax) 
                                VALUES (?, ?, ?, ?)
                            ''', batch_randomized_data)
                            batch_randomized_data = []  # 清空批处理列表
        
        # 处理剩余的数据
        if batch_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO typeMaterials 
                (typeid, categoryid, process_size, output_material, output_material_categoryid, 
                 output_material_groupid, output_quantity, output_material_name, output_material_icon) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
        
        # 处理剩余的randomizedMaterials数据
        if batch_randomized_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO typeRandomizedMaterials 
                (type_id, materialTypeID, quantityMin, quantityMax) 
                VALUES (?, ?, ?, ?)
            ''', batch_randomized_data)
        
        # 统计randomizedMaterials数量
        cursor.execute('SELECT COUNT(*) FROM typeRandomizedMaterials')
        randomized_count = cursor.fetchone()[0]
        
        print(f"[+] 已处理 {len(type_materials_data)} 个物品的材料数据，语言: {lang}")
        print(f"[+] 已处理 {randomized_count} 条随机材料数据，语言: {lang}")
    
    def process_type_materials_for_language(self, language: str) -> bool:
        """
        为指定语言处理typeMaterials数据
        """
        print(f"[+] 开始处理typeMaterials数据，语言: {language}")
        
        # 读取typeMaterials数据
        type_materials_data = self.read_type_materials_jsonl()
        if not type_materials_data:
            print("[x] 无法读取typeMaterials数据")
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
            self.process_type_materials_to_db(type_materials_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] typeMaterials数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理typeMaterials数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理typeMaterials数据
        """
        print("[+] 开始处理typeMaterials数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_type_materials_for_language(language):
                success_count += 1
        
        print(f"[+] typeMaterials数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 物品材料产出数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = TypeMaterialsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品材料产出数据处理器完成")


if __name__ == "__main__":
    main()

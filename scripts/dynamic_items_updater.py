#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态物品数据更新器模块
从网络获取动态物品属性数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any
from scripts.jsonl_loader import load_jsonl


def load_dynamic_items_from_sde(config) -> List[Dict[str, Any]]:
    """
    从SDE的dynamicItemAttributes.jsonl文件中加载动态物品数据
    """
    project_root = Path(__file__).parent.parent
    sde_input_path = project_root / config["paths"]["sde_input"]
    dynamic_items_file = sde_input_path / "dynamicItemAttributes.jsonl"
    
    if not dynamic_items_file.exists():
        print(f"[x] 未找到dynamicItemAttributes.jsonl文件: {dynamic_items_file}")
        return []
    
    print(f"[+] 从SDE加载动态物品数据: {dynamic_items_file}")
    
    # 使用我们的jsonl_loader加载数据
    data = load_jsonl(str(dynamic_items_file))
    
    if data:
        print(f"[+] 成功加载 {len(data)} 个动态物品")
    else:
        print("[x] dynamicItemAttributes.jsonl文件为空或加载失败")
    
    return data


def create_dynamic_items_tables(cursor: sqlite3.Cursor):
    """
    创建动态物品属性相关的表
    """
    print("[+] 创建动态物品数据表...")
    
    # 创建动态物品属性表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dynamic_item_attributes (
            type_id INTEGER,
            attribute_id INTEGER,
            min_value REAL,
            max_value REAL,
            PRIMARY KEY (type_id, attribute_id)
        )
    ''')

    # 创建动态物品映射表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dynamic_item_mappings (
            type_id INTEGER,
            applicable_type INTEGER,
            resulting_type INTEGER,
            PRIMARY KEY (type_id, applicable_type)
        )
    ''')
    
    print("[+] 动态物品数据表创建完成")


def process_dynamic_items_to_db(data: List[Dict[str, Any]], cursor: sqlite3.Cursor):
    """
    处理动态物品JSONL数据并插入到数据库
    """
    if not data:
        print("[!] 没有动态物品数据需要处理")
        return
    
    print(f"[+] 开始处理动态物品数据...")
    start_time = time.time()

    # 创建表
    create_dynamic_items_tables(cursor)
    
    # 清空现有数据
    cursor.execute('DELETE FROM dynamic_item_attributes')
    cursor.execute('DELETE FROM dynamic_item_mappings')

    # 用于批量插入的数据列表
    attributes_batch = []
    mappings_batch = []
    batch_size = 1000

    # 遍历所有动态物品
    for item_data in data:
        type_id = item_data.get("_key")
        if not type_id:
            continue
        
        # 处理属性数据 - JSONL格式是数组
        if "attributeIDs" in item_data:
            for attr_data in item_data["attributeIDs"]:
                attr_id = attr_data.get("_key")
                if attr_id:
                    attributes_batch.append((
                        type_id,
                        attr_id,
                        round(attr_data.get("min", 0.0), 4),
                        round(attr_data.get("max", 0.0), 4)
                    ))

        # 处理映射数据 - JSONL格式是数组
        if "inputOutputMapping" in item_data:
            for mapping in item_data["inputOutputMapping"]:
                resulting_type = mapping.get("resultingType")
                if resulting_type and "applicableTypes" in mapping:
                    for applicable_type in mapping["applicableTypes"]:
                        mappings_batch.append((
                            type_id,
                            applicable_type,
                            resulting_type
                        ))

        # 批量插入属性数据
        if len(attributes_batch) >= batch_size:
            cursor.executemany('''
                INSERT OR REPLACE INTO dynamic_item_attributes 
                (type_id, attribute_id, min_value, max_value)
                VALUES (?, ?, ?, ?)
            ''', attributes_batch)
            attributes_batch = []

        # 批量插入映射数据
        if len(mappings_batch) >= batch_size:
            cursor.executemany('''
                INSERT OR REPLACE INTO dynamic_item_mappings
                (type_id, applicable_type, resulting_type)
                VALUES (?, ?, ?)
            ''', mappings_batch)
            mappings_batch = []

    # 处理剩余的批次数据
    if attributes_batch:
        cursor.executemany('''
            INSERT OR REPLACE INTO dynamic_item_attributes 
            (type_id, attribute_id, min_value, max_value)
            VALUES (?, ?, ?, ?)
        ''', attributes_batch)

    if mappings_batch:
        cursor.executemany('''
            INSERT OR REPLACE INTO dynamic_item_mappings
            (type_id, applicable_type, resulting_type)
            VALUES (?, ?, ?)
        ''', mappings_batch)

    # 统计信息
    cursor.execute('SELECT COUNT(*) FROM dynamic_item_attributes')
    attr_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM dynamic_item_mappings')
    mapping_count = cursor.fetchone()[0]

    end_time = time.time()
    print(f"[+] 动态物品数据处理完成:")
    print(f"    - 属性记录: {attr_count} 条")
    print(f"    - 映射记录: {mapping_count} 条")
    print(f"    - 耗时: {end_time - start_time:.2f} 秒")


def update_all_databases(config):
    """更新所有语言的数据库"""
    project_root = Path(__file__).parent.parent
    db_output_path = project_root / config["paths"]["db_output"]
    languages = config.get("languages", ["en"])
    
    # 获取动态物品数据
    dynamic_data = load_dynamic_items_from_sde(config)
    if not dynamic_data:
        print("[x] 无法获取动态物品数据，跳过处理")
        return
    
    # 为每种语言创建数据库并处理数据
    for lang in languages:
        db_filename = db_output_path / f'item_db_{lang}.sqlite'
        
        print(f"\n[+] 处理数据库: {db_filename}")
        
        try:
            conn = sqlite3.connect(str(db_filename))
            cursor = conn.cursor()
            
            # 处理动态物品数据
            process_dynamic_items_to_db(dynamic_data, cursor)
            
            # 提交事务
            conn.commit()
            conn.close()
            
            print(f"[+] 数据库 {lang} 更新完成")
            
        except Exception as e:
            print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 动态物品数据更新器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 更新所有数据库
    update_all_databases(config)
    
    print("\n[+] 动态物品数据更新器完成")


if __name__ == "__main__":
    main()

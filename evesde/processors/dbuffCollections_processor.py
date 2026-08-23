#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dbuff集合数据处理器模块
用于处理dbuffCollections数据并写入数据库

功能: 处理dbuff集合数据，创建dbuffCollection表
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import wide_texts, names_row, name_cols_sql, names_ddl
import json
import sqlite3
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 操作名称映射到操作ID
OPERATION_MAP = {
    "preassign": -1,
    "premul": 0,
    "prediv": 1,
    "modadd": 2,
    "modsub": 3,
    "postmul": 4,
    "postdiv": 5,
    "postpercent": 6,
    "postassign": 7
}


class DbuffCollectionsProcessor:
    """dbuff集合数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化dbuffCollections处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_input"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_dbuff_collections_jsonl(self) -> Dict[str, Any]:
        """
        读取dbuffCollections JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "dbuffCollections.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到dbuffCollections JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取dbuffCollections JSONL文件: {jsonl_file}")
        
        dbuff_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为dbuff_id
                        dbuff_id = data['_key']
                        dbuff_data[dbuff_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(dbuff_data)} 个dbuffCollections记录")
            return dbuff_data
            
        except Exception as e:
            print(f"[x] 读取dbuffCollections JSONL文件时出错: {e}")
            return {}
    
    def create_dbuff_collection_table(self, cursor: sqlite3.Cursor):
        """创建dbuffCollection表（含 displayName 多语宽列）"""
        cursor.execute('DROP TABLE IF EXISTS dbuffCollection')
        cursor.execute(f'''
        CREATE TABLE dbuffCollection (
            dbuff_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            dbuff_name TEXT,
            {names_ddl()},
            aggregateMode TEXT,
            modifier_info TEXT,
            PRIMARY KEY (dbuff_id, type_id)
        ) WITHOUT ROWID
        ''')
        print("[+] 创建dbuffCollection表")
    
    def get_warfare_buff_mapping(self, cursor: sqlite3.Cursor) -> Tuple[Dict[int, int], Dict[int, List[Dict]]]:
        """
        从数据库获取warfare buff的映射关系
        
        Returns:
            dict: warfare buff ID到Value ID的映射
            dict: dbuff_id到type_id列表的映射
        """
        print("[+] 正在获取warfare buff映射关系...")
        
        # 获取所有warfare buff相关的attribute_id
        cursor.execute('''
            SELECT da.attribute_id, attribute_key
            FROM dogmaAttributes AS da
            WHERE attribute_key LIKE 'warfareBuff%'
        ''')
        
        warfare_attributes = cursor.fetchall()
        
        # 创建ID到Value的映射
        buff_mapping = {}
        buff_ids = []
        
        for attr_id, name in warfare_attributes:
            if name.endswith('ID'):
                # 提取数字部分，如 warfareBuff1ID -> 1
                buff_num = re.search(r'warfareBuff(\d+)ID', name)
                if buff_num:
                    buff_num = buff_num.group(1)
                    # 查找对应的Value属性
                    value_name = f"warfareBuff{buff_num}Value"
                    for v_attr_id, v_name in warfare_attributes:
                        if v_name == value_name:
                            buff_mapping[attr_id] = v_attr_id
                            buff_ids.append(attr_id)
                            break
        
        print(f"[+] 找到 {len(buff_mapping)} 个warfare buff映射关系")
        
        # 获取所有相关的type_id和dbuff_id关系
        type_dbuff_mapping = {}
        if buff_ids:
            placeholders = ','.join(['?' for _ in buff_ids])
            cursor.execute(f'''
                SELECT ta.type_id, ta.attribute_id, ta.value 
                FROM typeAttributes AS ta 
                WHERE attribute_id in ({placeholders}) and value > 0
            ''', buff_ids)
            
            warfare_results = cursor.fetchall()
            
            for type_id, attr_id, dbuff_id in warfare_results:
                dbuff_id = int(dbuff_id)
                if dbuff_id not in type_dbuff_mapping:
                    type_dbuff_mapping[dbuff_id] = []
                type_dbuff_mapping[dbuff_id].append({
                    'type_id': type_id,
                    'buff_attr_id': attr_id,
                    'value_attr_id': buff_mapping.get(attr_id, 0)
                })
            
            print(f"[+] 找到 {len(warfare_results)} 个type与dbuff的关联关系")
        
        return buff_mapping, type_dbuff_mapping
    
    def parse_modifiers(self, dbuff_data: Dict[str, Any], modifying_attribute_id: int) -> List[Dict]:
        """
        解析dbuff数据中的修饰器信息
        
        Args:
            dbuff_data: dbuff数据
            modifying_attribute_id: 修饰属性ID
            
        Returns:
            list: 修饰器列表
        """
        modifiers = []
        operation_str = dbuff_data.get('operationName', 'postMul').lower()
        if operation_str in OPERATION_MAP.keys():
            operation = OPERATION_MAP[operation_str]
        else:
            print(f"[!] 未找到 {operation_str} 的 operation, 使用默认值postmul")
            operation = 4  # 默认为postmul
        
        # 处理itemModifiers
        if 'itemModifiers' in dbuff_data and dbuff_data['itemModifiers']:
            for modifier in dbuff_data['itemModifiers']:
                if 'dogmaAttributeID' in modifier:
                    modifiers.append({
                        "domain": "shipID",
                        "func": "ItemModifier",
                        "modifiedAttributeID": modifier['dogmaAttributeID'],
                        "modifyingAttributeID": modifying_attribute_id,
                        "operation": operation
                    })
        
        # 处理locationModifiers
        if 'locationModifiers' in dbuff_data and dbuff_data['locationModifiers']:
            for modifier in dbuff_data['locationModifiers']:
                if 'dogmaAttributeID' in modifier:
                    modifiers.append({
                        "domain": "shipID",
                        "func": "LocationModifier",
                        "modifiedAttributeID": modifier['dogmaAttributeID'],
                        "modifyingAttributeID": modifying_attribute_id,
                        "operation": operation
                    })
        
        # 处理locationGroupModifiers
        if 'locationGroupModifiers' in dbuff_data and dbuff_data['locationGroupModifiers']:
            for modifier in dbuff_data['locationGroupModifiers']:
                if 'dogmaAttributeID' in modifier and 'groupID' in modifier:
                    modifiers.append({
                        "domain": "shipID",
                        "func": "LocationGroupModifier",
                        "modifiedAttributeID": modifier['dogmaAttributeID'],
                        "modifyingAttributeID": modifying_attribute_id,
                        "groupID": modifier['groupID'],
                        "operation": operation
                    })
        
        # 处理locationRequiredSkillModifiers
        if 'locationRequiredSkillModifiers' in dbuff_data and dbuff_data['locationRequiredSkillModifiers']:
            for modifier in dbuff_data['locationRequiredSkillModifiers']:
                if 'dogmaAttributeID' in modifier and 'skillID' in modifier:
                    modifiers.append({
                        "domain": "shipID",
                        "func": "LocationRequiredSkillModifier",
                        "modifiedAttributeID": modifier['dogmaAttributeID'],
                        "modifyingAttributeID": modifying_attribute_id,
                        "skillTypeID": modifier['skillID'],
                        "operation": operation
                    })
        
        return modifiers
    
    def process_dbuff_collections_to_db(self, dbuff_data: Dict[str, Any], cursor: sqlite3.Cursor, lang: str):
        """
        处理dbuffCollections数据并写入数据库
        完全按照old版本的逻辑
        """
        self.create_dbuff_collection_table(cursor)
        
        # 获取warfare buff映射关系
        buff_mapping, type_dbuff_mapping = self.get_warfare_buff_mapping(cursor)
        
        batch_data = []
        batch_size = 1000
        insert_sql = f'''
            INSERT OR REPLACE INTO dbuffCollection (
                dbuff_id, type_id, dbuff_name, {name_cols_sql()}, aggregateMode, modifier_info
            ) VALUES (?, ?, ?, {", ".join(["?"] * 8)}, ?, ?)
        '''

        for dbuff_id, dbuff_info in dbuff_data.items():
            dbuff_id = int(dbuff_id)

            # developerDescription 仅保留英文字母作为内部 dbuff_name
            if 'developerDescription' in dbuff_info:
                dbuff_name = re.sub(r'[^a-zA-Z]', '', dbuff_info['developerDescription'])
            else:
                dbuff_name = "dbuff_" + str(dbuff_id)

            display_names = wide_texts(dbuff_info.get('displayName'))
            aggregateMode = dbuff_info.get('aggregateMode')

            if dbuff_id not in type_dbuff_mapping:
                continue

            for type_info in type_dbuff_mapping[dbuff_id]:
                type_id = type_info['type_id']
                modifying_attribute_id = type_info['value_attr_id']
                modifiers = self.parse_modifiers(dbuff_info, modifying_attribute_id)
                batch_data.append((
                    dbuff_id, type_id, dbuff_name, *names_row(display_names),
                    aggregateMode, json.dumps(modifiers),
                ))
                if len(batch_data) >= batch_size:
                    cursor.executemany(insert_sql, batch_data)
                    batch_data = []

        if batch_data:
            cursor.executemany(insert_sql, batch_data)
        
        print(f"[+] 已处理 {len(dbuff_data)} 个dbuff集合，语言: {lang}")
    
    def process_dbuff_collections_for_language(self, language: str) -> bool:
        """
        为指定语言处理dbuffCollections数据
        """
        print(f"[+] 开始处理dbuffCollections数据，语言: {language}")
        
        # 读取dbuffCollections数据
        dbuff_data = self.read_dbuff_collections_jsonl()
        if not dbuff_data:
            print("[x] 无法读取dbuffCollections数据")
            return False
        
        # 数据库文件路径
        db_path = get_db_path(self.config)
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 处理数据
            self.process_dbuff_collections_to_db(dbuff_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] dbuffCollections数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理dbuffCollections数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理dbuffCollections数据
        """
        print("[+] 开始处理dbuffCollections数据")
        
        return self.process_dbuff_collections_for_language('en')


def main(config=None):
    """主函数"""
    print("[+] dbuff集合数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DbuffCollectionsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] dbuff集合数据处理器完成")


if __name__ == "__main__":
    main()

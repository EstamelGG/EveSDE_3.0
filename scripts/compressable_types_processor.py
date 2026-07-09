#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可压缩物品类型数据处理器模块
用于从SDE的jsonl文件中读取物品压缩对照表数据并存储到数据库

对应old版本: old/main.py中的fetch_compressable函数
功能: 从SDE的compressibleTypes.jsonl文件读取可压缩物品数据，创建compressible_types表
数据源: SDE的compressibleTypes.jsonl文件
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
import scripts.jsonl_loader as jsonl_loader


class CompressableTypesProcessor:
    """可压缩物品类型数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化可压缩物品类型处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_compressible_types_jsonl(self) -> Dict[int, int]:
        """
        读取compressibleTypes JSONL文件
        返回格式: {origin_id: compressed_id}
        """
        jsonl_file = self.sde_jsonl_path / "compressibleTypes.jsonl"
        
        # 使用统一的jsonl_loader加载数据
        compressible_list = jsonl_loader.load_jsonl(str(jsonl_file))
        
        if not compressible_list:
            print(f"[x] 未能读取到compressibleTypes数据")
            return {}
        
        compressible_data = {}
        for item in compressible_list:
            try:
                # _key 是原始物品ID，compressedTypeID 是压缩后的物品ID
                origin_id = item['_key']
                compressed_id = item['compressedTypeID']
                compressible_data[origin_id] = compressed_id
            except KeyError as e:
                print(f"[!] 记录缺少必要字段: {e}, 数据: {item}")
                continue
        
        print(f"[+] 成功处理 {len(compressible_data)} 条压缩对照数据")
        return compressible_data
    
    def create_compressible_types_table(self, cursor: sqlite3.Cursor):
        """创建compressible_types表"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS compressible_types (
            origin INTEGER NOT NULL,
            compressed INTEGER NOT NULL,
            PRIMARY KEY (origin)
        )
        ''')
        print("[+] 创建compressible_types表")
    
    def process_compressable_data_to_db(self, compressible_data: Dict[int, int], cursor: sqlite3.Cursor, lang: str):
        """处理可压缩物品数据并写入数据库"""
        try:
            # 创建表
            self.create_compressible_types_table(cursor)
            
            # 清空现有数据（如果有的话）
            cursor.execute('DELETE FROM compressible_types')
            
            # 插入新数据
            insert_count = 0
            for origin_id, compressed_id in compressible_data.items():
                cursor.execute(
                    'INSERT INTO compressible_types (origin, compressed) VALUES (?, ?)',
                    (origin_id, compressed_id)
                )
                insert_count += 1
            
            print(f"[+] 数据库 {lang}: 已创建/更新 compressible_types 表，插入了 {insert_count} 条记录")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_compressable_data_for_language(self, compressible_data: Dict[int, int], language: str) -> bool:
        """为指定语言处理可压缩物品数据"""
        print(f"[+] 开始处理可压缩物品数据，语言: {language}")
        
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
            self.process_compressable_data_to_db(compressible_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] 可压缩物品数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理可压缩物品数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """为所有语言处理可压缩物品数据"""
        print("[+] 开始处理可压缩物品数据")
        
        # 从SDE jsonl文件读取数据
        compressible_data = self.read_compressible_types_jsonl()
        
        if not compressible_data:
            print("[x] 未能读取到可压缩物品数据，处理终止")
            return False
        
        success_count = 0
        for language in self.languages:
            if self.process_compressable_data_for_language(compressible_data, language):
                success_count += 1
        
        print(f"[+] 可压缩物品数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 可压缩物品类型数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = CompressableTypesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 可压缩物品类型数据处理器完成")


if __name__ == "__main__":
    main()

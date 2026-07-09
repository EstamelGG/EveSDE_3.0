#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPC公司部门数据处理器模块
用于处理divisions数据并写入数据库

功能: 处理NPC公司部门数据，创建divisions表
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any


class DivisionsProcessor:
    """NPC公司部门数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化divisions处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def read_divisions_jsonl(self) -> Dict[str, Any]:
        """
        读取divisions JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "npcCorporationDivisions.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到divisions JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取divisions JSONL文件: {jsonl_file}")
        
        divisions_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为division_id
                        division_id = data['_key']
                        divisions_data[division_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(divisions_data)} 个divisions记录")
            return divisions_data
            
        except Exception as e:
            print(f"[x] 读取divisions JSONL文件时出错: {e}")
            return {}
    
    def create_divisions_table(self, cursor: sqlite3.Cursor):
        """
        创建divisions表
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS divisions (
            division_id INTEGER NOT NULL PRIMARY KEY,
            name TEXT
        )
        ''')
        print("[+] 创建divisions表")
    
    def process_divisions_to_db(self, divisions_data: Dict[str, Any], cursor: sqlite3.Cursor, language: str):
        """
        处理divisions数据并写入数据库
        """
        # 清空现有数据
        cursor.execute('DELETE FROM divisions')
        print(f"[+] 清空divisions表数据")
        
        # 处理每个部门
        processed_count = 0
        for division_id, division_data in divisions_data.items():
            # 获取当前语言的名称
            # 新版本使用'name'字段，包含多语言映射
            name = ''
            if 'name' in division_data:
                name = division_data['name'].get(language, division_data['name'].get('en', ''))
            
            # 插入数据
            cursor.execute('''
                INSERT OR REPLACE INTO divisions 
                (division_id, name)
                VALUES (?, ?)
            ''', (
                division_id, 
                name
            ))
            
            processed_count += 1
        
        print(f"[+] 成功处理 {processed_count} 个divisions记录")
    
    def process_divisions_for_language(self, language: str) -> bool:
        """
        为指定语言处理divisions数据
        """
        print(f"[+] 开始处理divisions数据，语言: {language}")
        
        # 读取divisions数据
        divisions_data = self.read_divisions_jsonl()
        if not divisions_data:
            print("[x] 无法读取divisions数据")
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
            
            # 创建表
            self.create_divisions_table(cursor)
            
            # 处理数据
            self.process_divisions_to_db(divisions_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] divisions数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理divisions数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理divisions数据
        """
        print("[+] 开始处理divisions数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_divisions_for_language(language):
                success_count += 1
        
        print(f"[+] divisions数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] NPC公司部门数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DivisionsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] NPC公司部门数据处理器完成")


if __name__ == "__main__":
    main()

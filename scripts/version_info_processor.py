#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本信息处理器
用于在所有语言的数据库中创建版本信息表，记录SDE的build number
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime


class VersionInfoProcessor:
    """版本信息处理器"""
    
    def __init__(self, config):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def create_version_info_table(self, cursor: sqlite3.Cursor):
        """
        创建版本信息表
        记录SDE的build number和相关信息
        """
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS version_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                build_number INTEGER NOT NULL,
                patch_number INTEGER DEFAULT 0,
                release_date TEXT,
                build_key TEXT,
                description TEXT DEFAULT 'EVE SDE Database Version Information'
            )
        ''')
        
        print("[+] 创建version_info表")
    
    def insert_version_info(self, cursor: sqlite3.Cursor, build_number, release_date: str = None, build_key: str = None):
        """
        插入版本信息到数据库
        支持格式：
        - 纯数字：2615149 -> build_number=2615149, patch_number=0
        - 带补丁：2615149.01 -> build_number=2615149, patch_number=1
        """
        # 先清空现有版本信息（只保留最新的）
        cursor.execute('DELETE FROM version_info')
        
        # 解析build_number和patch_number
        build_number_str = str(build_number)
        if '.' in build_number_str:
            # 格式：2615149.01
            base_number, patch_str = build_number_str.split('.', 1)
            base_number = int(base_number)
            patch_number = int(patch_str)
        else:
            # 格式：2615149
            base_number = int(build_number_str)
            patch_number = 0
        
        cursor.execute('''
            INSERT INTO version_info (build_number, patch_number, release_date, build_key)
            VALUES (?, ?, ?, ?)
        ''', (base_number, patch_number, release_date, build_key))
        
        if patch_number > 0:
            print(f"[+] 插入版本信息: build_number={base_number}, patch_number={patch_number}, release_date={release_date}")
        else:
            print(f"[+] 插入版本信息: build_number={base_number}, release_date={release_date}")
    
    def process_version_info_for_language(self, language: str, build_number, release_date: str = None, build_key: str = None) -> bool:
        """
        为指定语言处理版本信息
        """
        print(f"[+] 开始处理版本信息，语言: {language}")
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 创建版本信息表
            self.create_version_info_table(cursor)
            
            # 插入版本信息
            self.insert_version_info(cursor, build_number, release_date, build_key)
            
            # 提交更改
            conn.commit()
            print(f"[+] 版本信息处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理版本信息时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self, build_number, release_date: str = None, build_key: str = None) -> bool:
        """
        为所有语言处理版本信息
        """
        print("[+] 开始处理版本信息")
        
        success_count = 0
        for language in self.languages:
            if self.process_version_info_for_language(language, build_number, release_date, build_key):
                success_count += 1
        
        print(f"[+] 版本信息处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None, build_number=None, release_date=None, build_key=None):
    """主函数"""
    if not config:
        print("[x] 配置参数缺失")
        return False
    
    if not build_number:
        print("[x] build_number参数缺失")
        return False
    
    processor = VersionInfoProcessor(config)
    return processor.process_all_languages(build_number, release_date, build_key)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库标准化处理模块
用于确保SQLite数据库在跨平台环境下的一致性

解决macOS和Windows上生成的SQLite数据库MD5不同的问题
"""

import sqlite3
import tempfile
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any


class DatabaseNormalizer:
    """数据库标准化处理器"""
    
    # 标准化的PRAGMA设置，确保跨平台一致性
    STANDARD_PRAGMAS = {
        'journal_mode': 'DELETE',
        'synchronous': 'FULL',
        'cache_size': '-64000',
        'temp_store': 'MEMORY',
        'mmap_size': '0',
        'page_size': '4096',
        'auto_vacuum': 'NONE',
        'encoding': '"UTF-8"',
        'foreign_keys': 'OFF',
        'recursive_triggers': 'OFF',
        'secure_delete': 'OFF',
        'count_changes': 'OFF',
        'legacy_file_format': 'OFF',
        'full_column_names': 'OFF',
        'short_column_names': 'ON',
        'empty_result_callbacks': 'OFF',
        'case_sensitive_like': 'OFF',
        'checkpoint_fullfsync': 'OFF',
        'writable_schema': 'OFF',
        'optimize': 'OFF',
        'query_only': 'OFF',
        'read_uncommitted': 'OFF',
        'reverse_unordered_selects': 'OFF',
        'threads': '0',
        'user_version': '0',
        'application_id': '0',
    }
    
    def __init__(self, config: Dict[str, Any]):
        """初始化数据库标准化处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def create_standardized_connection(self, db_path: str) -> sqlite3.Connection:
        """创建标准化的数据库连接"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 应用标准化的PRAGMA设置
        for pragma_name, pragma_value in self.STANDARD_PRAGMAS.items():
            try:
                cursor.execute(f"PRAGMA {pragma_name} = {pragma_value}")
            except sqlite3.Error as e:
                print(f"[!] 设置PRAGMA {pragma_name} = {pragma_value} 失败: {e}")
        
        conn.commit()
        return conn
    
    def normalize_single_database(self, db_path: Path) -> bool:
        """标准化单个数据库文件"""
        try:
            print(f"[+] 标准化数据库: {db_path.name}")
            
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.sqlite')
            os.close(temp_fd)
            
            try:
                # 使用标准化连接打开源数据库
                with self.create_standardized_connection(str(db_path)) as source_conn:
                    # 使用标准化连接创建临时数据库
                    with self.create_standardized_connection(temp_path) as temp_conn:
                        # 备份数据库
                        source_conn.backup(temp_conn)
                        
                        # 执行标准化操作
                        cursor = temp_conn.cursor()
                        cursor.execute("VACUUM")
                        cursor.execute("ANALYZE")
                        temp_conn.commit()
                        # 确保连接被完全关闭
                        cursor.close()
                    temp_conn.close()
                source_conn.close()

                # 验证临时文件是否创建成功
                if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                    raise Exception("临时数据库文件创建失败或为空")
                # 安全替换原文件：先生成新文件，删除旧文件，重命名新文件
                print(f"[+] 安全替换数据库文件: {db_path.name}")
                
                # 1. 删除原文件
                if db_path.exists():
                    os.remove(db_path)
                    print(f"[+] 已删除原文件: {db_path.name}")
                
                # 2. 重命名临时文件为目标文件
                shutil.move(temp_path, db_path)
                print(f"[+] 已重命名临时文件为: {db_path.name}")
                
                # 3. 验证最终文件
                if not db_path.exists():
                    raise Exception("最终数据库文件不存在")
                
                print(f"[+] 数据库标准化完成: {db_path.name}")
                return True
                
            except Exception as e:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    print(f"[!] 已清理临时文件: {temp_path}")
                raise e
                
        except Exception as e:
            print(f"[x] 数据库标准化失败 {db_path.name}: {e}")
            return False
    
    def normalize_all_databases(self) -> bool:
        """标准化所有数据库文件，确保跨平台一致性"""
        print("[+] 开始标准化所有数据库文件...")
        
        success_count = 0
        total_count = 0
        
        # 处理所有语言的数据库
        for lang in self.languages:
            db_path = self.db_output_path / f'item_db_{lang}.sqlite'
            
            if not db_path.exists():
                print(f"[!] 数据库文件不存在: {db_path}")
                continue
            
            total_count += 1
            if self.normalize_single_database(db_path):
                success_count += 1
        
        print(f"[+] 数据库标准化完成: {success_count}/{total_count} 个成功")
        return success_count == total_count


def normalize_all_databases(config: Dict[str, Any]) -> bool:
    """
    便捷函数：标准化所有数据库文件
    
    Args:
        config: 配置字典
        
    Returns:
        bool: 是否全部成功
    """
    normalizer = DatabaseNormalizer(config)
    return normalizer.normalize_all_databases()


def main(config: Dict[str, Any] = None):
    """主函数"""
    print("[+] 数据库标准化处理器启动")
    
    if not config:
        # 如果没有传入配置，则尝试加载本地配置
        try:
            import json
            config_path = Path(__file__).parent.parent / "config.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"[x] 无法加载配置文件: {e}")
            return False
    
    # 执行数据库标准化
    success = normalize_all_databases(config)
    
    if success:
        print("[+] 所有数据库标准化完成")
    else:
        print("[!] 部分数据库标准化失败")
    
    return success


if __name__ == "__main__":
    main()

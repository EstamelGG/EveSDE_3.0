#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库MD5标准化工具
比对两个SQLite数据库的MD5，如果不同则通过各种方法消除差异

功能:
1. 计算两个SQLite数据库的MD5
2. 如果MD5不同，尝试多种标准化方法
3. 输出标准化后的新数据库文件
"""

import sqlite3
import hashlib
import os
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional, Dict, Any


class SQLiteMD5Normalizer:
    """SQLite数据库MD5标准化器"""
    
    # 标准化的PRAGMA设置
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
    
    def __init__(self, db1_path: str, db2_path: str):
        """初始化标准化器"""
        self.db1_path = Path(db1_path)
        self.db2_path = Path(db2_path)
        
        # 检查文件是否存在
        if not self.db1_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db1_path}")
        if not self.db2_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db2_path}")
    
    def calculate_md5(self, file_path: Path) -> str:
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def get_database_info(self, db_path: Path) -> Dict[str, Any]:
        """获取数据库信息"""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 获取表列表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        # 获取每个表的记录数
        table_counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            table_counts[table] = cursor.fetchone()[0]
        
        # 获取PRAGMA信息
        pragma_info = {}
        for pragma_name in ['journal_mode', 'synchronous', 'page_size', 'encoding', 'auto_vacuum']:
            cursor.execute(f"PRAGMA {pragma_name}")
            pragma_info[pragma_name] = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'tables': tables,
            'table_counts': table_counts,
            'pragma_info': pragma_info
        }
    
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
    
    def normalize_database_method1(self, source_path: Path, output_path: Path) -> bool:
        """方法1: 使用标准化PRAGMA + VACUUM + ANALYZE"""
        try:
            print(f"[+] 方法1: 标准化PRAGMA + VACUUM + ANALYZE")
            
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.sqlite')
            os.close(temp_fd)
            
            try:
                # 使用标准化连接打开源数据库
                with self.create_standardized_connection(str(source_path)) as source_conn:
                    # 使用标准化连接创建临时数据库
                    with self.create_standardized_connection(temp_path) as temp_conn:
                        # 备份数据库
                        source_conn.backup(temp_conn)
                        
                        # 执行标准化操作
                        cursor = temp_conn.cursor()
                        cursor.execute("VACUUM")
                        cursor.execute("ANALYZE")
                        temp_conn.commit()
                
                # 移动到输出路径
                shutil.move(temp_path, output_path)
                return True
                
            except Exception as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise e
                
        except Exception as e:
            print(f"[x] 方法1失败: {e}")
            return False
    
    def normalize_database_method2(self, source_path: Path, output_path: Path) -> bool:
        """方法2: 导出SQL并重新创建数据库"""
        try:
            print(f"[+] 方法2: 导出SQL并重新创建")
            
            # 创建临时SQL文件
            temp_fd, temp_sql_path = tempfile.mkstemp(suffix='.sql')
            os.close(temp_fd)
            
            try:
                # 导出SQL
                with sqlite3.connect(str(source_path)) as conn:
                    with open(temp_sql_path, 'w', encoding='utf-8') as f:
                        for line in conn.iterdump():
                            f.write(line + '\n')
                
                # 创建新的标准化数据库
                with self.create_standardized_connection(str(output_path)) as conn:
                    cursor = conn.cursor()
                    
                    # 执行SQL
                    with open(temp_sql_path, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                        cursor.executescript(sql_content)
                    
                    # 执行标准化操作
                    cursor.execute("VACUUM")
                    cursor.execute("ANALYZE")
                    conn.commit()
                
                return True
                
            finally:
                if os.path.exists(temp_sql_path):
                    os.unlink(temp_sql_path)
                
        except Exception as e:
            print(f"[x] 方法2失败: {e}")
            return False
    
    def normalize_database_method3(self, source_path: Path, output_path: Path) -> bool:
        """方法3: 逐表复制数据"""
        try:
            print(f"[+] 方法3: 逐表复制数据")
            
            # 获取源数据库信息
            source_info = self.get_database_info(source_path)
            
            # 创建新的标准化数据库
            with self.create_standardized_connection(str(output_path)) as conn:
                cursor = conn.cursor()
                
                # 复制每个表
                for table in source_info['tables']:
                    # 获取表结构
                    with sqlite3.connect(str(source_path)) as source_conn:
                        source_cursor = source_conn.cursor()
                        source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                        create_sql = source_cursor.fetchone()[0]
                        
                        # 创建表
                        cursor.execute(create_sql)
                        
                        # 复制数据
                        source_cursor.execute(f"SELECT * FROM {table}")
                        rows = source_cursor.fetchall()
                        
                        if rows:
                            # 获取列名
                            source_cursor.execute(f"PRAGMA table_info({table})")
                            columns = [col[1] for col in source_cursor.fetchall()]
                            placeholders = ', '.join(['?' for _ in columns])
                            insert_sql = f"INSERT INTO {table} VALUES ({placeholders})"
                            
                            cursor.executemany(insert_sql, rows)
                
                # 执行标准化操作
                cursor.execute("VACUUM")
                cursor.execute("ANALYZE")
                conn.commit()
            
            return True
            
        except Exception as e:
            print(f"[x] 方法3失败: {e}")
            return False
    
    def normalize_database(self, source_path: Path, output_path: Path) -> bool:
        """尝试多种方法标准化数据库"""
        methods = [
            self.normalize_database_method1,
            self.normalize_database_method2,
            self.normalize_database_method3
        ]
        
        for i, method in enumerate(methods, 1):
            try:
                if method(source_path, output_path):
                    print(f"[+] 方法{i}成功")
                    return True
            except Exception as e:
                print(f"[x] 方法{i}异常: {e}")
                continue
        
        print(f"[x] 所有标准化方法都失败了")
        return False
    
    def compare_and_normalize(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        比对并标准化数据库
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (是否成功, 输出文件1路径, 输出文件2路径)
        """
        print("[+] 开始比对SQLite数据库MD5")
        print("=" * 50)
        
        # 计算MD5
        md5_1 = self.calculate_md5(self.db1_path)
        md5_2 = self.calculate_md5(self.db2_path)
        
        print(f"[+] 数据库1 MD5: {md5_1}")
        print(f"[+] 数据库2 MD5: {md5_2}")
        
        if md5_1 == md5_2:
            print("[+] MD5相同，无需标准化")
            return True, None, None
        
        print("[!] MD5不同，开始标准化处理")
        
        # 显示数据库信息
        print("\n[+] 数据库信息对比:")
        info1 = self.get_database_info(self.db1_path)
        info2 = self.get_database_info(self.db2_path)
        
        print(f"    数据库1表数量: {len(info1['tables'])}")
        print(f"    数据库2表数量: {len(info2['tables'])}")
        
        # 检查表差异
        tables_diff = set(info1['tables']) ^ set(info2['tables'])
        if tables_diff:
            print(f"[!] 表结构差异: {tables_diff}")
        
        # 检查记录数差异
        common_tables = set(info1['tables']) & set(info2['tables'])
        for table in common_tables:
            count1 = info1['table_counts'][table]
            count2 = info2['table_counts'][table]
            if count1 != count2:
                print(f"[!] 表{table}记录数差异: {count1} vs {count2}")
        
        # 生成输出文件路径
        output1_path = self.db1_path.parent / f"{self.db1_path.stem}_normalized.sqlite"
        output2_path = self.db2_path.parent / f"{self.db2_path.stem}_normalized.sqlite"
        
        print(f"\n[+] 开始标准化数据库1: {output1_path}")
        success1 = self.normalize_database(self.db1_path, output1_path)
        
        print(f"\n[+] 开始标准化数据库2: {output2_path}")
        success2 = self.normalize_database(self.db2_path, output2_path)
        
        if success1 and success2:
            # 验证标准化后的MD5
            new_md5_1 = self.calculate_md5(output1_path)
            new_md5_2 = self.calculate_md5(output2_path)
            
            print(f"\n[+] 标准化后MD5:")
            print(f"    数据库1: {new_md5_1}")
            print(f"    数据库2: {new_md5_2}")
            
            if new_md5_1 == new_md5_2:
                print("[+] 标准化成功！两个数据库MD5现在相同")
                return True, str(output1_path), str(output2_path)
            else:
                print("[!] 标准化后MD5仍然不同")
                return False, str(output1_path), str(output2_path)
        else:
            print("[x] 标准化失败")
            return False, None, None


def main():
    """主函数"""
    # 硬编码的数据库路径
    db1_path = "/Users/gg/Documents/tmp/new.sqlite"
    db2_path = "/Users/gg/Documents/tmp/old.sqlite"
    
    print("[+] SQLite数据库MD5标准化工具")
    print("=" * 50)
    print(f"[+] 数据库1: {db1_path}")
    print(f"[+] 数据库2: {db2_path}")
    
    try:
        # 创建标准化器
        normalizer = SQLiteMD5Normalizer(db1_path, db2_path)
        
        # 执行比对和标准化
        success, output1, output2 = normalizer.compare_and_normalize()
        
        print("\n" + "=" * 50)
        if success:
            if output1 and output2:
                print("[+] 标准化完成!")
                print(f"    📁 标准化数据库1: {output1}")
                print(f"    📁 标准化数据库2: {output2}")
            else:
                print("[+] 数据库已经一致，无需标准化")
        else:
            print("[x] 标准化失败")
        
    except FileNotFoundError as e:
        print(f"[x] 错误: {e}")
    except Exception as e:
        print(f"[x] 处理过程中出错: {e}")


if __name__ == "__main__":
    main()

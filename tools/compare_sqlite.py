#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库对比工具
基于sqldiff思想，比较两个SQLite数据库的结构和数据差异
生成SQL脚本来同步数据库差异
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
import json
import subprocess
import tempfile


class SQLiteComparator:
    """SQLite数据库对比器"""
    
    def __init__(self, db1_path: str, db2_path: str):
        """初始化对比器"""
        self.db1_path = Path(db1_path)
        self.db2_path = Path(db2_path)
        
        # 检查文件是否存在
        if not self.db1_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db1_path}")
        if not self.db2_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db2_path}")
    
    def get_connection(self, db_path: Path) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(db_path))
    
    def get_tables(self, conn: sqlite3.Connection) -> List[str]:
        """获取数据库中的所有表名"""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_schema(self, conn: sqlite3.Connection, table_name: str) -> str:
        """获取表的创建语句"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        result = cursor.fetchone()
        return result[0] if result else ""
    
    def get_table_info(self, conn: sqlite3.Connection, table_name: str) -> List[Tuple]:
        """获取表的列信息"""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        return cursor.fetchall()
    
    def get_table_count(self, conn: sqlite3.Connection, table_name: str) -> int:
        """获取表的记录数"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        return cursor.fetchone()[0]
    
    def get_table_sample(self, conn: sqlite3.Connection, table_name: str, limit: int = 5) -> List[Tuple]:
        """获取表的样本数据"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM '{table_name}' LIMIT {limit}")
        return cursor.fetchall()
    
    def compare_schemas(self) -> Dict[str, Any]:
        """对比数据库结构"""
        print("[+] 对比数据库结构...")
        
        with self.get_connection(self.db1_path) as conn1, self.get_connection(self.db2_path) as conn2:
            tables1 = set(self.get_tables(conn1))
            tables2 = set(self.get_tables(conn2))
            
            result = {
                "tables_only_in_db1": list(tables1 - tables2),
                "tables_only_in_db2": list(tables2 - tables1),
                "common_tables": list(tables1 & tables2),
                "table_differences": {}
            }
            
            # 对比共同表的结构
            for table in result["common_tables"]:
                schema1 = self.get_table_schema(conn1, table)
                schema2 = self.get_table_schema(conn2, table)
                
                if schema1 != schema2:
                    result["table_differences"][table] = {
                        "db1_schema": schema1,
                        "db2_schema": schema2
                    }
            
            return result
    
    def compare_data(self, table_name: str) -> Dict[str, Any]:
        """对比表的数据"""
        print(f"[+] 对比表 {table_name} 的数据...")
        
        with self.get_connection(self.db1_path) as conn1, self.get_connection(self.db2_path) as conn2:
            count1 = self.get_table_count(conn1, table_name)
            count2 = self.get_table_count(conn2, table_name)
            
            result = {
                "table_name": table_name,
                "db1_count": count1,
                "db2_count": count2,
                "count_difference": count2 - count1,
                "samples": {
                    "db1": self.get_table_sample(conn1, table_name),
                    "db2": self.get_table_sample(conn2, table_name)
                }
            }
            
            return result
    
    def generate_report(self) -> str:
        """生成对比报告"""
        print("[+] 生成对比报告...")
        
        # 对比结构
        schema_diff = self.compare_schemas()
        
        # 对比数据
        data_diffs = {}
        for table in schema_diff["common_tables"]:
            data_diffs[table] = self.compare_data(table)
        
            report = []
        report.append("=" * 60)
        report.append("SQLite数据库对比报告")
        report.append("=" * 60)
        report.append(f"数据库1: {self.db1_path}")
        report.append(f"数据库2: {self.db2_path}")
        report.append("")
        
        # 表结构差异
        report.append("📋 表结构对比:")
        report.append("-" * 30)
        
        if schema_diff["tables_only_in_db1"]:
            report.append(f"仅在数据库1中的表: {', '.join(schema_diff['tables_only_in_db1'])}")
        
        if schema_diff["tables_only_in_db2"]:
            report.append(f"仅在数据库2中的表: {', '.join(schema_diff['tables_only_in_db2'])}")
        
        if schema_diff["table_differences"]:
            report.append("表结构不同的表:")
            for table, diff in schema_diff["table_differences"].items():
                report.append(f"  - {table}")
        
        if not any([schema_diff["tables_only_in_db1"], schema_diff["tables_only_in_db2"], schema_diff["table_differences"]]):
            report.append("✅ 所有表结构相同")
        
        report.append("")
        
        # 数据对比
        report.append("📊 数据对比:")
        report.append("-" * 30)
        
        for table, data_diff in data_diffs.items():
            report.append(f"表: {table}")
            report.append(f"  数据库1记录数: {data_diff['db1_count']}")
            report.append(f"  数据库2记录数: {data_diff['db2_count']}")
            
            if data_diff['count_difference'] != 0:
                report.append(f"  差异: {data_diff['count_difference']:+d}")
            else:
                report.append("  ✅ 记录数相同")
            
            report.append("")
        
        return "\n".join(report)
    
    def generate_sync_sql(self, table_name: str = None) -> str:
        """生成同步SQL脚本（基于sqldiff思想）"""
        print(f"[+] 生成同步SQL脚本...")
        
        sql_statements = []
        sql_statements.append("-- SQLite数据库同步脚本")
        sql_statements.append(f"-- 将 {self.db1_path.name} 同步到 {self.db2_path.name}")
        sql_statements.append("-- 基于sqldiff思想生成")
        sql_statements.append("")
        
        with self.get_connection(self.db1_path) as conn1, self.get_connection(self.db2_path) as conn2:
            # 获取表列表
            tables1 = set(self.get_tables(conn1))
            tables2 = set(self.get_tables(conn2))
            
            # 处理只在db1中存在的表（需要删除）
            tables_only_in_db1 = tables1 - tables2
            for table in tables_only_in_db1:
                sql_statements.append(f"-- 删除只在源数据库中存在的表: {table}")
                sql_statements.append(f"DROP TABLE IF EXISTS '{table}';")
                sql_statements.append("")
            
            # 处理只在db2中存在的表（需要创建）
            tables_only_in_db2 = tables2 - tables1
            for table in tables_only_in_db2:
                sql_statements.append(f"-- 创建只在目标数据库中存在的表: {table}")
                schema = self.get_table_schema(conn2, table)
                if schema:
                    sql_statements.append(f"{schema};")
                sql_statements.append("")
            
            # 处理共同表的数据差异
            common_tables = tables1 & tables2
            if table_name:
                common_tables = [t for t in common_tables if t == table_name]
            
            for table in common_tables:
                sql_statements.append(f"-- 同步表: {table}")
                
                # 获取表结构信息
                info1 = self.get_table_info(conn1, table)
                info2 = self.get_table_info(conn2, table)
                
                # 检查结构是否相同
                if info1 != info2:
                    sql_statements.append(f"-- 警告: 表 {table} 结构不同，需要手动处理")
                    sql_statements.append(f"-- 源数据库结构: {len(info1)} 列")
                    sql_statements.append(f"-- 目标数据库结构: {len(info2)} 列")
                    sql_statements.append("")
                    continue
                
                # 获取主键信息
                primary_keys = [col[1] for col in info1 if col[5]]  # col[5] 是 pk 字段
                
                if not primary_keys:
                    sql_statements.append(f"-- 警告: 表 {table} 没有主键，无法进行精确同步")
                    sql_statements.append("")
                    continue
                
                # 生成数据同步SQL
                self._generate_table_sync_sql(conn1, conn2, table, primary_keys, sql_statements)
                sql_statements.append("")
        
        return "\n".join(sql_statements)
    
    def _generate_table_sync_sql(self, conn1: sqlite3.Connection, conn2: sqlite3.Connection, 
                                table: str, primary_keys: List[str], sql_statements: List[str]):
        """为单个表生成同步SQL"""
        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()
        
        # 获取所有数据
        cursor1.execute(f"SELECT * FROM '{table}'")
        rows1 = {tuple(row): row for row in cursor1.fetchall()}
        
        cursor2.execute(f"SELECT * FROM '{table}'")
        rows2 = {tuple(row): row for row in cursor2.fetchall()}
        
        # 获取列名
        cursor1.execute(f"PRAGMA table_info('{table}')")
        columns = [col[1] for col in cursor1.fetchall()]
        
        # 找出差异
        only_in_db1 = rows1.keys() - rows2.keys()
        only_in_db2 = rows2.keys() - rows1.keys()
        common_rows = rows1.keys() & rows2.keys()
        
        # 生成INSERT语句（只在db1中存在的行）
        if only_in_db1:
            sql_statements.append(f"-- 插入只在源数据库中存在的行 ({len(only_in_db1)} 行)")
            for row_key in only_in_db1:
                row = rows1[row_key]
                values = ', '.join([f"'{str(v)}'" if v is not None else 'NULL' for v in row])
                sql_statements.append(f"INSERT OR REPLACE INTO '{table}' VALUES ({values});")
        
        # 生成DELETE语句（只在db2中存在的行）
        if only_in_db2:
            sql_statements.append(f"-- 删除只在目标数据库中存在的行 ({len(only_in_db2)} 行)")
            for row_key in only_in_db2:
                row = rows2[row_key]
                # 使用主键构建WHERE条件
                where_conditions = []
                for pk in primary_keys:
                    pk_index = columns.index(pk)
                    pk_value = row[pk_index]
                    if pk_value is not None:
                        where_conditions.append(f"'{pk}' = '{pk_value}'")
                    else:
                        where_conditions.append(f"'{pk}' IS NULL")
                
                if where_conditions:
                    sql_statements.append(f"DELETE FROM '{table}' WHERE {' AND '.join(where_conditions)};")
        
        # 生成UPDATE语句（内容不同的行）
        updated_count = 0
        for row_key in common_rows:
            row1 = rows1[row_key]
            row2 = rows2[row_key]
            
            if row1 != row2:
                updated_count += 1
                # 找出不同的列
                different_columns = []
                for i, (col1, col2) in enumerate(zip(row1, row2)):
                    if col1 != col2:
                        col_name = columns[i]
                        value = f"'{str(col1)}'" if col1 is not None else 'NULL'
                        different_columns.append(f"'{col_name}' = {value}")
                
                if different_columns:
                    # 使用主键构建WHERE条件
                    where_conditions = []
                    for pk in primary_keys:
                        pk_index = columns.index(pk)
                        pk_value = row1[pk_index]
                        if pk_value is not None:
                            where_conditions.append(f"'{pk}' = '{pk_value}'")
                        else:
                            where_conditions.append(f"'{pk}' IS NULL")
                    
                    if where_conditions:
                        sql_statements.append(f"UPDATE '{table}' SET {', '.join(different_columns)} WHERE {' AND '.join(where_conditions)};")
        
        if updated_count > 0:
            sql_statements.insert(-len(sql_statements), f"-- 更新内容不同的行 ({updated_count} 行)")
    
    def save_report(self, output_path: str = None):
        """保存对比报告到文件"""
        report = self.generate_report()
        
        if output_path is None:
            output_path = f"sqlite_comparison_report_{self.db1_path.stem}_vs_{self.db2_path.stem}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"[+] 对比报告已保存到: {output_path}")
        return output_path
    
    def save_sync_sql(self, output_path: str = None, table_name: str = None):
        """保存同步SQL脚本到文件"""
        sql_script = self.generate_sync_sql(table_name)
        
        if output_path is None:
            output_path = f"sqlite_sync_{self.db1_path.stem}_to_{self.db2_path.stem}.sql"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sql_script)
        
        print(f"[+] 同步SQL脚本已保存到: {output_path}")
        return output_path


def main():
    """主函数"""
    # 硬编码的数据库路径
    db1_path = "/Users/gg/Documents/tmp/1.7.5.sqlite"
    db2_path = "/Users/gg/Documents/tmp/1.8.1.sqlite"
    
    print("[+] SQLite数据库对比工具 (基于sqldiff思想)")
    print("=" * 50)
    
    try:
        # 创建对比器
        comparator = SQLiteComparator(db1_path, db2_path)
        
        # 生成并显示报告
        report = comparator.generate_report()
        print(report)
        
        # 保存报告
        report_file = comparator.save_report()
        
        # 生成并保存同步SQL脚本
        sql_file = comparator.save_sync_sql()
        
        print(f"\n[+] 对比完成!")
        print(f"    📋 对比报告: {report_file}")
        print(f"    🔧 同步SQL脚本: {sql_file}")
        print(f"\n[!] 使用说明:")
        print(f"    1. 查看对比报告了解差异")
        print(f"    2. 检查同步SQL脚本")
        print(f"    3. 执行SQL脚本同步数据库:")
        print(f"       sqlite3 target.db < {sql_file}")
        
    except FileNotFoundError as e:
        print(f"[x] 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[x] 对比过程中出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

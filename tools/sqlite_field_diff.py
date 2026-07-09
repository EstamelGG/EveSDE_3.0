#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite字段级差异对比工具
类似git diff，显示具体字段的前后差异
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
import json
from difflib import unified_diff


class SQLiteFieldDiff:
    """SQLite字段级差异对比器"""
    
    def __init__(self, db1_path: str, db2_path: str):
        """初始化对比器"""
        self.db1_path = Path(db1_path)
        self.db2_path = Path(db2_path)
        
        # 硬编码开关：是否记录图片差异
        self.IGNORE_IMAGE_DIFFERENCES = True
        # 硬编码开关：是否忽略主键差异
        self.IGNORE_PRIMARY_KEY_DIFFERENCES = True
        
        # 检查文件是否存在
        if not self.db1_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db1_path}")
        if not self.db2_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db2_path}")
    
    def get_connection(self, db_path: Path) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(db_path))
    
    def is_image_value(self, value: Any) -> bool:
        """检查值是否为图片文件（.png结尾）"""
        if not isinstance(value, str):
            return False
        return value.lower().endswith('.png')
    
    def get_tables(self, conn: sqlite3.Connection) -> List[str]:
        """获取数据库中的所有表名"""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_info(self, conn: sqlite3.Connection, table_name: str) -> List[Tuple]:
        """获取表的列信息"""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        return cursor.fetchall()
    
    def get_primary_keys(self, conn: sqlite3.Connection, table_name: str) -> List[str]:
        """获取表的主键列名"""
        table_info = self.get_table_info(conn, table_name)
        return [col[1] for col in table_info if col[5]]  # col[5] 是 pk 字段
    
    def get_table_data(self, conn: sqlite3.Connection, table_name: str) -> Dict[Tuple, Tuple]:
        """获取表数据，以主键为key，完整行数据为value"""
        cursor = conn.cursor()
        table_info = self.get_table_info(conn, table_name)
        primary_keys = self.get_primary_keys(conn, table_name)
        
        if not primary_keys:
            # 如果没有主键，使用rowid
            cursor.execute(f"SELECT rowid, * FROM '{table_name}'")
            return {row[0]: row[1:] for row in cursor.fetchall()}
        
        # 获取主键列的索引
        pk_indices = [i for i, col in enumerate(table_info) if col[5]]
        
        cursor.execute(f"SELECT * FROM '{table_name}'")
        result = {}
        for row in cursor.fetchall():
            pk_values = tuple(row[i] for i in pk_indices)
            result[pk_values] = row
        
        return result
    
    def format_row_diff(self, row1: Tuple, row2: Tuple, columns: List[str], 
                       primary_keys: List[str]) -> List[str]:
        """格式化行差异，类似git diff"""
        if row1 == row2:
            return []
        
        diff_lines = []
        has_non_ignored_differences = False
        
        # 逐列比较，先检查是否有非忽略的差异
        for i, (col1, col2) in enumerate(zip(row1, row2)):
            if col1 != col2:
                col_name = columns[i]
                
                # 如果启用了忽略主键差异，且当前字段是主键，则跳过
                if (self.IGNORE_PRIMARY_KEY_DIFFERENCES and 
                    col_name in primary_keys):
                    continue
                
                # 如果启用了忽略图片差异，且两个值都是图片文件，则跳过
                if (self.IGNORE_IMAGE_DIFFERENCES and 
                    self.is_image_value(col1) and 
                    self.is_image_value(col2)):
                    continue
                
                has_non_ignored_differences = True
                break
        
        # 如果没有非忽略的差异，返回空列表
        if not has_non_ignored_differences:
            return []
        
        # 获取主键列的索引
        pk_indices = [i for i, col in enumerate(columns) if col in primary_keys]
        
        # 显示主键信息（包含字段名）
        pk_info = []
        for i, pk_col in enumerate(primary_keys):
            pk_index = columns.index(pk_col)
            pk_value = row1[pk_index]
            pk_info.append(f"{pk_col}={pk_value}")
        diff_lines.append(f"@@ 主键: {', '.join(pk_info)} @@")
        
        # 逐列比较，显示差异
        for i, (col1, col2) in enumerate(zip(row1, row2)):
            if col1 != col2:
                col_name = columns[i]
                
                # 如果启用了忽略主键差异，且当前字段是主键，则跳过
                if (self.IGNORE_PRIMARY_KEY_DIFFERENCES and 
                    col_name in primary_keys):
                    continue
                
                # 如果启用了忽略图片差异，且两个值都是图片文件，则跳过
                if (self.IGNORE_IMAGE_DIFFERENCES and 
                    self.is_image_value(col1) and 
                    self.is_image_value(col2)):
                    continue
                
                diff_lines.append(f"  {col_name}:")
                diff_lines.append(f"    - {col1}")
                diff_lines.append(f"    + {col2}")
        
        return diff_lines
    
    def compare_table_fields(self, table_name: str) -> Dict[str, Any]:
        """对比表的字段级差异"""
        print(f"[+] 对比表 {table_name} 的字段差异...")
        
        with self.get_connection(self.db1_path) as conn1, self.get_connection(self.db2_path) as conn2:
            # 获取表结构
            info1 = self.get_table_info(conn1, table_name)
            info2 = self.get_table_info(conn2, table_name)
            
            if info1 != info2:
                return {
                    "error": f"表 {table_name} 结构不同，无法进行字段级对比",
                    "db1_columns": len(info1),
                    "db2_columns": len(info2)
                }
            
            # 获取列名
            columns = [col[1] for col in info1]
            primary_keys = self.get_primary_keys(conn1, table_name)
            
            # 获取数据
            data1 = self.get_table_data(conn1, table_name)
            data2 = self.get_table_data(conn2, table_name)
            
            # 找出差异
            only_in_db1 = data1.keys() - data2.keys()
            only_in_db2 = data2.keys() - data1.keys()
            common_keys = data1.keys() & data2.keys()
            
            result = {
                "table_name": table_name,
                "columns": columns,
                "primary_keys": primary_keys,
                "only_in_db1": [],
                "only_in_db2": [],
                "field_differences": [],
                "summary": {
                    "total_rows_db1": len(data1),
                    "total_rows_db2": len(data2),
                    "only_in_db1_count": len(only_in_db1),
                    "only_in_db2_count": len(only_in_db2),
                    "field_diff_count": 0
                }
            }
            
            # 处理只在db1中的行
            for pk in only_in_db1:
                row = data1[pk]
                result["only_in_db1"].append({
                    "primary_key": pk,
                    "row_data": row
                })
            
            # 处理只在db2中的行
            for pk in only_in_db2:
                row = data2[pk]
                result["only_in_db2"].append({
                    "primary_key": pk,
                    "row_data": row
                })
            
            # 处理字段差异
            for pk in common_keys:
                row1 = data1[pk]
                row2 = data2[pk]
                
                if row1 != row2:
                    field_diff = self.format_row_diff(row1, row2, columns, primary_keys)
                    if field_diff:
                        result["field_differences"].append({
                            "primary_key": pk,
                            "diff_lines": field_diff
                        })
                        result["summary"]["field_diff_count"] += 1
            
            return result
    
    def generate_field_diff_report(self, table_name: str = None) -> str:
        """生成字段级差异报告"""
        print("[+] 生成字段级差异报告...")
        
        with self.get_connection(self.db1_path) as conn1, self.get_connection(self.db2_path) as conn2:
            tables1 = set(self.get_tables(conn1))
            tables2 = set(self.get_tables(conn2))
            
            # 确定要对比的表
            if table_name:
                if table_name not in tables1 or table_name not in tables2:
                    return f"错误: 表 {table_name} 在某个数据库中不存在"
                tables_to_compare = [table_name]
            else:
                tables_to_compare = list(tables1 & tables2)
            
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("SQLite字段级差异报告 (类似git diff)")
            report_lines.append("=" * 80)
            report_lines.append(f"数据库1: {self.db1_path}")
            report_lines.append(f"数据库2: {self.db2_path}")
            report_lines.append(f"图片差异忽略: {'是' if self.IGNORE_IMAGE_DIFFERENCES else '否'}")
            report_lines.append(f"主键差异忽略: {'是' if self.IGNORE_PRIMARY_KEY_DIFFERENCES else '否'}")
            report_lines.append("")
            
            total_differences = 0
            
            for table in tables_to_compare:
                result = self.compare_table_fields(table)
                
                if "error" in result:
                    report_lines.append(f"❌ {result['error']}")
                    report_lines.append("")
                    continue
                
                report_lines.append(f"📋 表: {table}")
                report_lines.append("-" * 50)
                
                # 显示统计信息
                summary = result["summary"]
                report_lines.append(f"记录数: {summary['total_rows_db1']} → {summary['total_rows_db2']}")
                report_lines.append(f"新增行: {summary['only_in_db1_count']}")
                report_lines.append(f"删除行: {summary['only_in_db2_count']}")
                report_lines.append(f"字段差异: {summary['field_diff_count']}")
                report_lines.append("")
                
                # 显示新增的行
                if result["only_in_db1"]:
                    report_lines.append("➕ 新增的行:")
                    for item in result["only_in_db1"][:5]:  # 只显示前5个
                        pk_info = []
                        for i, pk_col in enumerate(result["primary_keys"]):
                            pk_value = item["primary_key"][i]
                            pk_info.append(f"{pk_col}={pk_value}")
                        pk_str = ', '.join(pk_info)
                        report_lines.append(f"  主键: {pk_str}")
                        report_lines.append(f"  数据: {item['row_data']}")
                    if len(result["only_in_db1"]) > 5:
                        report_lines.append(f"  ... 还有 {len(result['only_in_db1']) - 5} 行")
                    report_lines.append("")
                
                # 显示删除的行
                if result["only_in_db2"]:
                    report_lines.append("➖ 删除的行:")
                    for item in result["only_in_db2"][:5]:  # 只显示前5个
                        pk_info = []
                        for i, pk_col in enumerate(result["primary_keys"]):
                            pk_value = item["primary_key"][i]
                            pk_info.append(f"{pk_col}={pk_value}")
                        pk_str = ', '.join(pk_info)
                        report_lines.append(f"  主键: {pk_str}")
                        report_lines.append(f"  数据: {item['row_data']}")
                    if len(result["only_in_db2"]) > 5:
                        report_lines.append(f"  ... 还有 {len(result['only_in_db2']) - 5} 行")
                    report_lines.append("")
                
                # 显示字段差异
                if result["field_differences"]:
                    report_lines.append("🔄 字段差异:")
                    for item in result["field_differences"][:10]:  # 只显示前10个
                        pk_info = []
                        for i, pk_col in enumerate(result["primary_keys"]):
                            pk_value = item["primary_key"][i]
                            pk_info.append(f"{pk_col}={pk_value}")
                        pk_str = ', '.join(pk_info)
                        report_lines.append(f"  主键: {pk_str}")
                        for line in item["diff_lines"]:
                            report_lines.append(f"    {line}")
                        report_lines.append("")
                    
                    if len(result["field_differences"]) > 10:
                        report_lines.append(f"  ... 还有 {len(result['field_differences']) - 10} 个字段差异")
                    report_lines.append("")
                
                total_differences += (summary['only_in_db1_count'] + 
                                   summary['only_in_db2_count'] + 
                                   summary['field_diff_count'])
            
            # 总结
            report_lines.append("=" * 80)
            report_lines.append(f"总计差异: {total_differences} 处")
            if total_differences == 0:
                report_lines.append("✅ 两个数据库完全相同")
            report_lines.append("=" * 80)
            
            return "\n".join(report_lines)
    
    def save_field_diff_report(self, table_name: str = None, output_path: str = None):
        """保存字段级差异报告"""
        report = self.generate_field_diff_report(table_name)
        
        if output_path is None:
            suffix = f"_{table_name}" if table_name else ""
            output_path = f"sqlite_field_diff{suffix}_{self.db1_path.stem}_vs_{self.db2_path.stem}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"[+] 字段级差异报告已保存到: {output_path}")
        return output_path


def main():
    """主函数"""
    # 硬编码的数据库路径
    db1_path = "/Users/gg/Documents/tmp/1.7.5.sqlite"
    db2_path = "/Users/gg/Documents/tmp/1.8.sqlite"
    
    print("[+] SQLite字段级差异对比工具 (类似git diff)")
    print("=" * 60)
    
    try:
        # 创建对比器
        diff_tool = SQLiteFieldDiff(db1_path, db2_path)
        
        # 生成并显示报告
        report = diff_tool.generate_field_diff_report()
        print(report)
        
        # 保存报告
        output_file = diff_tool.save_field_diff_report()
        
        print(f"\n[+] 字段级差异对比完成，报告已保存到: {output_file}")
        
    except FileNotFoundError as e:
        print(f"[x] 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[x] 对比过程中出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

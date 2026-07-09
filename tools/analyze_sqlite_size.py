#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库大小分析工具
分析数据库中每个表和每列的数据大小，帮助识别占用空间最大的数据
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict


class SQLiteSizeAnalyzer:
    """SQLite数据库大小分析器"""
    
    def __init__(self, db_path: str):
        """初始化分析器"""
        self.db_path = Path(db_path)
        
        # 检查文件是否存在
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))
    
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
    
    def calculate_value_size(self, value: Any) -> int:
        """计算单个值的大小（字节）"""
        if value is None:
            return 0
        
        if isinstance(value, bytes):
            return len(value)
        elif isinstance(value, str):
            # SQLite 使用 UTF-8 编码
            return len(value.encode('utf-8'))
        elif isinstance(value, (int, float)):
            # 整数和浮点数在 SQLite 中的存储大小
            if isinstance(value, int):
                # SQLite 整数: 1, 2, 3, 4, 6, 8 字节
                if -128 <= value <= 127:
                    return 1
                elif -32768 <= value <= 32767:
                    return 2
                elif -2147483648 <= value <= 2147483647:
                    return 4
                elif -9223372036854775808 <= value <= 9223372036854775807:
                    return 8
                else:
                    return 8  # 大整数
            else:
                return 8  # REAL 类型，8 字节
        else:
            # 其他类型转换为字符串计算
            return len(str(value).encode('utf-8'))
    
    def calculate_column_size(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> int:
        """计算表中某一列的总大小"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT `{column_name}` FROM '{table_name}'")
        
        total_size = 0
        for row in cursor.fetchall():
            value = row[0]
            total_size += self.calculate_value_size(value)
        
        return total_size
    
    def calculate_table_data_size(self, conn: sqlite3.Connection, table_name: str) -> Dict[str, Any]:
        """计算表的数据大小和每列的大小"""
        print(f"  [*] 分析表: {table_name}")
        
        # 获取列信息
        table_info = self.get_table_info(conn, table_name)
        columns = [col[1] for col in table_info]  # col[1] 是列名
        
        # 获取记录数
        row_count = self.get_table_count(conn, table_name)
        
        # 计算每列的大小
        column_sizes = {}
        total_table_size = 0
        
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM '{table_name}'")
        
        # 初始化列大小计数器
        for col_name in columns:
            column_sizes[col_name] = 0
        
        # 逐行计算
        processed_rows = 0
        for row in cursor.fetchall():
            for i, value in enumerate(row):
                if i < len(columns):
                    col_name = columns[i]
                    size = self.calculate_value_size(value)
                    column_sizes[col_name] += size
                    total_table_size += size
            
            processed_rows += 1
            # 每处理 10000 行显示一次进度
            if processed_rows % 10000 == 0:
                print(f"    [*] 已处理 {processed_rows}/{row_count} 行...")
        
        return {
            "table_name": table_name,
            "row_count": row_count,
            "total_size": total_table_size,
            "column_sizes": column_sizes,
            "columns": columns
        }
    
    def get_database_file_size(self) -> int:
        """获取数据库文件的大小"""
        return self.db_path.stat().st_size
    
    def analyze_database(self) -> Dict[str, Any]:
        """分析整个数据库"""
        print("[+] 开始分析数据库...")
        print(f"[+] 数据库路径: {self.db_path}")
        print(f"[+] 数据库文件大小: {self._format_size(self.get_database_file_size())}")
        print("")
        
        with self.get_connection() as conn:
            # 获取所有表
            tables = self.get_tables(conn)
            print(f"[+] 发现 {len(tables)} 个表")
            print("")
            
            # 分析每个表
            table_analyses = []
            for table in tables:
                try:
                    analysis = self.calculate_table_data_size(conn, table)
                    table_analyses.append(analysis)
                except Exception as e:
                    print(f"  [x] 分析表 {table} 时出错: {e}")
                    continue
            
            return {
                "database_path": str(self.db_path),
                "database_file_size": self.get_database_file_size(),
                "table_count": len(tables),
                "tables": table_analyses
            }
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """生成分析报告"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("SQLite数据库大小分析报告")
        report_lines.append("=" * 80)
        report_lines.append(f"数据库路径: {analysis['database_path']}")
        report_lines.append(f"数据库文件大小: {self._format_size(analysis['database_file_size'])}")
        report_lines.append(f"表数量: {analysis['table_count']}")
        report_lines.append("")
        
        # 按表总大小排序
        sorted_tables = sorted(
            analysis['tables'],
            key=lambda x: x['total_size'],
            reverse=True
        )
        
        # 汇总所有列的大小（跨表）
        all_column_sizes = defaultdict(int)
        for table_analysis in analysis['tables']:
            for col_name, col_size in table_analysis['column_sizes'].items():
                all_column_sizes[col_name] += col_size
        
        # 按列总大小排序（跨表）
        sorted_columns = sorted(
            all_column_sizes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 1. 表大小排名
        report_lines.append("📊 表大小排名（按数据大小）:")
        report_lines.append("-" * 80)
        total_data_size = 0
        for i, table_analysis in enumerate(sorted_tables, 1):
            size = table_analysis['total_size']
            total_data_size += size
            percentage = (size / analysis['database_file_size']) * 100 if analysis['database_file_size'] > 0 else 0
            report_lines.append(
                f"{i:3d}. {table_analysis['table_name']:40s} "
                f"{self._format_size(size):>12s} "
                f"({table_analysis['row_count']:>10,} 行, {percentage:>5.2f}%)"
            )
        report_lines.append(f"\n    数据总大小: {self._format_size(total_data_size)}")
        report_lines.append("")
        
        # 2. 列大小排名（跨表）
        report_lines.append("📊 列大小排名（跨所有表，按数据大小）:")
        report_lines.append("-" * 80)
        for i, (col_name, col_size) in enumerate(sorted_columns[:50], 1):  # 只显示前50
            percentage = (col_size / total_data_size) * 100 if total_data_size > 0 else 0
            report_lines.append(
                f"{i:3d}. {col_name:40s} "
                f"{self._format_size(col_size):>12s} "
                f"({percentage:>5.2f}%)"
            )
        if len(sorted_columns) > 50:
            report_lines.append(f"\n    ... 还有 {len(sorted_columns) - 50} 个列未显示")
        report_lines.append("")
        
        # 3. 每个表的详细信息
        report_lines.append("📋 每个表的详细信息:")
        report_lines.append("-" * 80)
        for table_analysis in sorted_tables:
            report_lines.append(f"\n表: {table_analysis['table_name']}")
            report_lines.append(f"  记录数: {table_analysis['row_count']:,}")
            report_lines.append(f"  总大小: {self._format_size(table_analysis['total_size'])}")
            
            # 按列大小排序
            sorted_cols = sorted(
                table_analysis['column_sizes'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            report_lines.append("  列大小排名:")
            for i, (col_name, col_size) in enumerate(sorted_cols[:10], 1):  # 每表只显示前10列
                percentage = (col_size / table_analysis['total_size']) * 100 if table_analysis['total_size'] > 0 else 0
                report_lines.append(
                    f"    {i:2d}. {col_name:30s} "
                    f"{self._format_size(col_size):>12s} "
                    f"({percentage:>5.2f}%)"
                )
            if len(sorted_cols) > 10:
                report_lines.append(f"    ... 还有 {len(sorted_cols) - 10} 个列未显示")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, analysis: Dict[str, Any], output_path: str = None):
        """保存分析报告到文件"""
        report = self.generate_report(analysis)
        
        if output_path is None:
            output_path = f"sqlite_size_analysis_{self.db_path.stem}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"[+] 分析报告已保存到: {output_path}")
        return output_path


def main():
    """主函数"""
    # 硬编码的数据库路径
    db_path = '/Users/gg/Documents/GitHub/EVE-Nexus/EVE Nexus/utils/sde/db/item_db_zh.sqlite'
    
    print("[+] SQLite数据库大小分析工具")
    print("=" * 60)
    
    try:
        # 创建分析器
        analyzer = SQLiteSizeAnalyzer(db_path)
        
        # 分析数据库
        analysis = analyzer.analyze_database()
        
        # 生成并显示报告
        report = analyzer.generate_report(analysis)
        print("\n" + report)
        
        # 保存报告
        report_file = analyzer.save_report(analysis)
        
        print(f"\n[+] 分析完成!")
        print(f"    📋 分析报告: {report_file}")
        
    except FileNotFoundError as e:
        print(f"[x] 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[x] 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

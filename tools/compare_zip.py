#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZIP文件比对工具
比较两个ZIP文件的内容，检查文件是否存在以及文件哈希是否相同
"""

import zipfile
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional


class ZipComparator:
    """ZIP文件对比器"""
    
    def __init__(self, zip1_path: str, zip2_path: str):
        """初始化对比器"""
        self.zip1_path = Path(zip1_path)
        self.zip2_path = Path(zip2_path)
        
        # 检查文件是否存在
        if not self.zip1_path.exists():
            raise FileNotFoundError(f"ZIP文件不存在: {zip1_path}")
        if not self.zip2_path.exists():
            raise FileNotFoundError(f"ZIP文件不存在: {zip2_path}")
    
    def get_zip_file_info(self, zip_path: Path) -> Dict[str, Dict[str, Any]]:
        """获取ZIP文件中的所有文件信息"""
        file_info = {}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_name in zip_file.namelist():
                    # 跳过目录
                    if file_name.endswith('/'):
                        continue
                    
                    # 获取文件信息
                    info = zip_file.getinfo(file_name)
                    
                    # 计算文件哈希
                    with zip_file.open(file_name) as f:
                        file_content = f.read()
                        file_hash = hashlib.md5(file_content).hexdigest()
                    
                    file_info[file_name] = {
                        'size': info.file_size,
                        'compressed_size': info.compress_size,
                        'crc32': info.CRC,
                        'md5_hash': file_hash,
                        'modified_time': info.date_time
                    }
        
        except zipfile.BadZipFile:
            raise ValueError(f"无效的ZIP文件: {zip_path}")
        except Exception as e:
            raise RuntimeError(f"读取ZIP文件失败 {zip_path}: {e}")
        
        return file_info
    
    def compare_zip_files(self) -> Dict[str, Any]:
        """对比两个ZIP文件"""
        print("[+] 开始对比ZIP文件...")
        
        # 获取两个ZIP文件的信息
        print(f"[+] 读取ZIP文件1: {self.zip1_path}")
        zip1_info = self.get_zip_file_info(self.zip1_path)
        
        print(f"[+] 读取ZIP文件2: {self.zip2_path}")
        zip2_info = self.get_zip_file_info(self.zip2_path)
        
        # 获取文件列表
        files1 = set(zip1_info.keys())
        files2 = set(zip2_info.keys())
        
        # 找出差异
        only_in_zip1 = files1 - files2
        only_in_zip2 = files2 - files1
        common_files = files1 & files2
        
        # 检查共同文件的哈希差异
        hash_differences = []
        for file_name in common_files:
            if zip1_info[file_name]['md5_hash'] != zip2_info[file_name]['md5_hash']:
                hash_differences.append({
                    'file_name': file_name,
                    'zip1_hash': zip1_info[file_name]['md5_hash'],
                    'zip2_hash': zip2_info[file_name]['md5_hash'],
                    'zip1_size': zip1_info[file_name]['size'],
                    'zip2_size': zip2_info[file_name]['size']
                })
        
        result = {
            'zip1_path': str(self.zip1_path),
            'zip2_path': str(self.zip2_path),
            'zip1_file_count': len(files1),
            'zip2_file_count': len(files2),
            'only_in_zip1': list(only_in_zip1),
            'only_in_zip2': list(only_in_zip2),
            'common_files': list(common_files),
            'hash_differences': hash_differences,
            'summary': {
                'total_files_zip1': len(files1),
                'total_files_zip2': len(files2),
                'only_in_zip1_count': len(only_in_zip1),
                'only_in_zip2_count': len(only_in_zip2),
                'common_files_count': len(common_files),
                'hash_diff_count': len(hash_differences),
                'identical_files_count': len(common_files) - len(hash_differences)
            }
        }
        
        return result
    
    def generate_comparison_report(self) -> str:
        """生成对比报告"""
        print("[+] 生成对比报告...")
        
        comparison_result = self.compare_zip_files()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ZIP文件对比报告")
        report_lines.append("=" * 80)
        report_lines.append(f"ZIP文件1: {comparison_result['zip1_path']}")
        report_lines.append(f"ZIP文件2: {comparison_result['zip2_path']}")
        report_lines.append("")
        
        # 统计信息
        summary = comparison_result['summary']
        report_lines.append("📊 统计信息:")
        report_lines.append("-" * 30)
        report_lines.append(f"ZIP文件1文件数: {summary['total_files_zip1']}")
        report_lines.append(f"ZIP文件2文件数: {summary['total_files_zip2']}")
        report_lines.append(f"共同文件数: {summary['common_files_count']}")
        report_lines.append(f"仅在ZIP1中的文件: {summary['only_in_zip1_count']}")
        report_lines.append(f"仅在ZIP2中的文件: {summary['only_in_zip2_count']}")
        report_lines.append(f"哈希不同的文件: {summary['hash_diff_count']}")
        report_lines.append(f"完全相同的文件: {summary['identical_files_count']}")
        report_lines.append("")
        
        # 仅在ZIP1中的文件
        if comparison_result['only_in_zip1']:
            report_lines.append("➕ 仅在ZIP文件1中的文件:")
            report_lines.append("-" * 30)
            for file_name in sorted(comparison_result['only_in_zip1']):
                report_lines.append(f"  {file_name}")
            report_lines.append("")
        
        # 仅在ZIP2中的文件
        if comparison_result['only_in_zip2']:
            report_lines.append("➖ 仅在ZIP文件2中的文件:")
            report_lines.append("-" * 30)
            for file_name in sorted(comparison_result['only_in_zip2']):
                report_lines.append(f"  {file_name}")
            report_lines.append("")
        
        # 哈希不同的文件
        if comparison_result['hash_differences']:
            report_lines.append("🔄 哈希不同的文件:")
            report_lines.append("-" * 30)
            for diff in comparison_result['hash_differences']:
                report_lines.append(f"  文件: {diff['file_name']}")
                report_lines.append(f"    ZIP1 MD5: {diff['zip1_hash']} (大小: {diff['zip1_size']} 字节)")
                report_lines.append(f"    ZIP2 MD5: {diff['zip2_hash']} (大小: {diff['zip2_size']} 字节)")
                report_lines.append("")
        
        # 总结
        report_lines.append("=" * 80)
        total_differences = (summary['only_in_zip1_count'] + 
                           summary['only_in_zip2_count'] + 
                           summary['hash_diff_count'])
        
        if total_differences == 0:
            report_lines.append("✅ 两个ZIP文件完全相同")
        else:
            report_lines.append(f"❌ 发现 {total_differences} 处差异")
            if summary['only_in_zip1_count'] > 0:
                report_lines.append(f"   - {summary['only_in_zip1_count']} 个文件仅在ZIP1中")
            if summary['only_in_zip2_count'] > 0:
                report_lines.append(f"   - {summary['only_in_zip2_count']} 个文件仅在ZIP2中")
            if summary['hash_diff_count'] > 0:
                report_lines.append(f"   - {summary['hash_diff_count']} 个文件内容不同")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, output_path: str = None) -> str:
        """保存对比报告到文件"""
        report = self.generate_comparison_report()
        
        if output_path is None:
            output_path = f"zip_comparison_{self.zip1_path.stem}_vs_{self.zip2_path.stem}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"[+] 对比报告已保存到: {output_path}")
        return output_path
    
    def is_identical(self) -> bool:
        """检查两个ZIP文件是否完全相同"""
        comparison_result = self.compare_zip_files()
        summary = comparison_result['summary']
        
        return (summary['only_in_zip1_count'] == 0 and 
                summary['only_in_zip2_count'] == 0 and 
                summary['hash_diff_count'] == 0)




def main():
    """主函数"""
    # 硬编码的ZIP文件路径
    # 注意：请确保这两个ZIP文件存在，或者根据需要修改路径
    zip1_path = "D:\\tmp\\new\\icons.zip"
    zip2_path = "D:\\tmp\\old\\icons.zip"
    
    print("[+] ZIP文件比对工具")
    print("=" * 30)
    
    try:
        # 创建对比器
        comparator = ZipComparator(zip1_path, zip2_path)
        
        # 生成并显示报告
        report = comparator.generate_comparison_report()
        print(report)
        
        # 保存报告
        output_file = comparator.save_report()
        
        # 检查是否相同
        is_identical = comparator.is_identical()
        
        print(f"\n[+] 对比完成!")
        print(f"    📋 对比报告: {output_file}")
        if is_identical:
            print(f"    ✅ 两个ZIP文件完全相同")
        else:
            print(f"    ❌ 两个ZIP文件存在差异")
        
    except FileNotFoundError as e:
        print(f"[x] 错误: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[x] 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[x] 对比过程中出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


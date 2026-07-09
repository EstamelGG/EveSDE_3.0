#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONL文件比对工具
比较两个目录中的同名JSONL文件，以_key字段作为行索引
不受行顺序影响，找出存在差异的key
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Set, Tuple, Any, Optional
from collections import defaultdict


def load_jsonl_file(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    加载JSONL文件，以_key字段作为索引构建字典
    
    Args:
        file_path: JSONL文件路径
        
    Returns:
        以_key为键的字典
    """
    result = {}
    line_num = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    obj = json.loads(line)
                    if '_key' not in obj:
                        print(f"[!] 警告: 第 {line_num} 行缺少 '_key' 字段，跳过")
                        continue
                    
                    key = obj['_key']
                    if key in result:
                        print(f"[!] 警告: 第 {line_num} 行 '_key' 重复: {key}，覆盖之前的记录")
                    
                    result[key] = obj
                    
                except json.JSONDecodeError as e:
                    print(f"[!] 警告: 第 {line_num} 行JSON解析失败: {e}，跳过")
                    continue
                    
    except FileNotFoundError:
        print(f"[x] 文件不存在: {file_path}")
        return {}
    except Exception as e:
        print(f"[x] 读取文件失败 {file_path}: {e}")
        return {}
    
    return result


def compare_jsonl_files(
    file1_path: Path,
    file2_path: Path,
    verbose: bool = False,
    show_output: bool = True
) -> Tuple[bool, Set[str], Set[str], Dict[str, Tuple[Dict, Dict]]]:
    """
    比较两个JSONL文件
    
    Args:
        file1_path: 第一个JSONL文件路径
        file2_path: 第二个JSONL文件路径
        verbose: 是否显示详细差异
        show_output: 是否输出信息（如果为False，只返回结果不输出）
        
    Returns:
        (是否有差异, 只在file1中的keys, 只在file2中的keys, 值不同的keys及其差异)
    """
    # 加载文件
    data1 = load_jsonl_file(file1_path)
    data2 = load_jsonl_file(file2_path)
    
    keys1 = set(data1.keys())
    keys2 = set(data2.keys())
    
    # 找出只在file1中的keys
    only_in_file1 = keys1 - keys2
    
    # 找出只在file2中的keys
    only_in_file2 = keys2 - keys1
    
    # 找出共同的keys
    common_keys = keys1 & keys2
    
    # 找出值不同的keys
    different_keys = {}
    for key in common_keys:
        if data1[key] != data2[key]:
            different_keys[key] = (data1[key], data2[key])
    
    # 判断是否有差异
    has_difference = bool(only_in_file1 or only_in_file2 or different_keys)
    
    # 只在有差异且需要输出时才显示
    if has_difference and show_output:
        print(f"\n[!] 文件差异: {file1_path.name}")
        print(f"    文件1: {file1_path}")
        print(f"    文件2: {file2_path}")
        
        # 输出统计信息
        print(f"\n[+] 统计信息:")
        print(f"    文件1总记录数: {len(data1)}")
        print(f"    文件2总记录数: {len(data2)}")
        print(f"    共同记录数: {len(common_keys)}")
        print(f"    只在文件1中: {len(only_in_file1)}")
        print(f"    只在文件2中: {len(only_in_file2)}")
        print(f"    值不同的记录: {len(different_keys)}")
        
        # 输出差异详情
        if only_in_file1:
            print(f"\n[!] 只在文件1中的keys ({len(only_in_file1)} 个):")
            for key in sorted(only_in_file1):
                print(f"    - {key}")
        
        if only_in_file2:
            print(f"\n[!] 只在文件2中的keys ({len(only_in_file2)} 个):")
            for key in sorted(only_in_file2):
                print(f"    - {key}")
        
        if different_keys:
            print(f"\n[!] 值不同的keys ({len(different_keys)} 个):")
            for key in sorted(different_keys.keys()):
                val1, val2 = different_keys[key]
                print(f"    - {key}")
                if verbose:
                    print(f"      文件1: {json.dumps(val1, ensure_ascii=False, indent=8)}")
                    print(f"      文件2: {json.dumps(val2, ensure_ascii=False, indent=8)}")
                else:
                    # 显示不同字段及其具体值
                    all_fields = set(val1.keys()) | set(val2.keys())
                    diff_fields = []
                    for field in sorted(all_fields):
                        v1 = val1.get(field)
                        v2 = val2.get(field)
                        if v1 != v2:
                            diff_fields.append(field)
                            # 显示字段差异
                            v1_str = json.dumps(v1, ensure_ascii=False) if v1 is not None else "null"
                            v2_str = json.dumps(v2, ensure_ascii=False) if v2 is not None else "null"
                            # 如果值太长，截断显示
                            max_len = 100
                            if len(v1_str) > max_len:
                                v1_str = v1_str[:max_len] + "..."
                            if len(v2_str) > max_len:
                                v2_str = v2_str[:max_len] + "..."
                            print(f"      {field}:")
                            print(f"        文件1: {v1_str}")
                            print(f"        文件2: {v2_str}")
                    
                    if not diff_fields:
                        # 这种情况不应该发生，但作为保险
                        print(f"      所有字段相同（但对象不同）")
    
    return has_difference, only_in_file1, only_in_file2, different_keys


def find_jsonl_files(directory: Path) -> Dict[str, Path]:
    """
    查找目录中的所有JSONL文件
    
    Args:
        directory: 目录路径
        
    Returns:
        文件名到路径的映射
    """
    jsonl_files = {}
    if not directory.exists():
        return jsonl_files
    
    for file_path in directory.glob("*.jsonl"):
        jsonl_files[file_path.name] = file_path
    
    return jsonl_files


def compare_directories(
    dir1: Path,
    dir2: Path,
    verbose: bool = False
) -> bool:
    """
    比较两个目录中的同名JSONL文件
    
    Args:
        dir1: 第一个目录路径
        dir2: 第二个目录路径
        verbose: 是否显示详细差异
        
    Returns:
        是否有差异（True表示有差异，False表示无差异）
    """
    print("[+] JSONL文件比对工具")
    print("=" * 50)
    
    # 检查目录是否存在
    if not dir1.exists():
        print(f"[x] 目录不存在: {dir1}")
        return True
    
    if not dir2.exists():
        print(f"[x] 目录不存在: {dir2}")
        return True
    
    # 查找所有JSONL文件
    files1 = find_jsonl_files(dir1)
    files2 = find_jsonl_files(dir2)
    
    if not files1:
        print(f"[!] 目录1中没有找到JSONL文件: {dir1}")
        return True
    
    if not files2:
        print(f"[!] 目录2中没有找到JSONL文件: {dir2}")
        return True
    
    print(f"\n[+] 目录1中的JSONL文件: {len(files1)} 个")
    print(f"[+] 目录2中的JSONL文件: {len(files2)} 个")
    print(f"[+] 开始比较...\n")
    
    # 找出需要比较的文件（在dir1中的文件）
    files_to_compare = sorted(files1.keys())
    
    has_differences = False
    
    # 比较每个文件
    for filename in files_to_compare:
        file1_path = files1[filename]
        
        if filename not in files2:
            print(f"[!] 文件 '{filename}' 在目录2中不存在")
            has_differences = True
            continue
        
        file2_path = files2[filename]
        
        # 先静默检查是否有差异
        has_diff, only_in_1, only_in_2, different = compare_jsonl_files(
            file1_path, file2_path, verbose, show_output=False
        )
        
        # 只在有差异时才输出
        if has_diff:
            compare_jsonl_files(
                file1_path, file2_path, verbose, show_output=True
            )
            has_differences = True
    
    # 检查dir2中有但dir1中没有的文件
    only_in_dir2 = set(files2.keys()) - set(files1.keys())
    if only_in_dir2:
        print(f"\n[!] 目录2中有但目录1中没有的文件 ({len(only_in_dir2)} 个):")
        for filename in sorted(only_in_dir2):
            print(f"    - {filename}")
        has_differences = True
    
    return has_differences


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='JSONL文件比对工具 - 比较两个目录中的同名JSONL文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s dir1 dir2                    # 比较两个目录中的同名JSONL文件
  %(prog)s dir1 dir2 --verbose          # 显示详细的差异内容
        """
    )
    parser.add_argument(
        'dir1',
        type=str,
        help='第一个目录路径'
    )
    parser.add_argument(
        'dir2',
        type=str,
        help='第二个目录路径'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细的差异内容（包括完整的JSON对象）'
    )
    
    args = parser.parse_args()
    
    dir1 = Path(args.dir1)
    dir2 = Path(args.dir2)
    
    try:
        has_differences = compare_directories(dir1, dir2, args.verbose)
        
        if has_differences:
            print("\n" + "=" * 50)
            print("[x] 发现差异")
            sys.exit(1)
        else:
            print("\n" + "=" * 50)
            print("[+] 所有文件内容相同，无差异")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n[x] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


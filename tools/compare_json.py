#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON文件比对工具
使用jsondiff库进行简单的JSON文件比对
"""

import json
import sys
from pathlib import Path
import jsondiff


def load_json_file(file_path: str):
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[x] 文件不存在: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[x] JSON格式错误 {file_path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[x] 读取文件失败 {file_path}: {e}")
        sys.exit(1)


def main():
    """主函数"""
    # 硬编码的文件路径
    file1 = "/Users/gg/Documents/GitHub/EveSDE_2.0/output/localization/accountingentrytypes_localized.json"
    file2 = "/Users/gg/Documents/GitHub/EveSDE/accounting_entry_types/output/accountingentrytypes_localized.json"
    
    print("[+] JSON文件比对工具")
    print("=" * 30)
    
    # 检查文件是否存在
    if not Path(file1).exists():
        print(f"[x] 文件不存在: {file1}")
        sys.exit(1)
    
    if not Path(file2).exists():
        print(f"[x] 文件不存在: {file2}")
        sys.exit(1)
    
    # 加载文件
    data1 = load_json_file(file1)
    data2 = load_json_file(file2)
    
    # 使用jsondiff比对（忽略数组顺序）
    diff = jsondiff.diff(data1, data2, marshal=True)
    
    if not diff:
        print("[+] 两个JSON文件内容相同")
        sys.exit(0)
    else:
        print("[x] 两个JSON文件内容不同")
        print("\n[!] 差异详情:")
        print(json.dumps(diff, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
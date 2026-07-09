#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理脚本
删除所有缓存和输出目录，用于全部重新构造
"""

import shutil
import os
from pathlib import Path


def clean_python_cache():
    """使用os.walk清理Python缓存文件 - 更高效的方式"""
    print("[+] 清理Python缓存文件...")
    
    pyc_count = 0
    pycache_count = 0
    
    for root, dirs, files in os.walk('.'):
        # 删除__pycache__目录
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                pycache_count += 1
                print(f"[+] 已删除: {cache_path}")
            except Exception as e:
                print(f"[!] 删除失败 {cache_path}: {e}")
        
        # 删除独立的.pyc文件
        for file in files:
            if file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    pyc_count += 1
                    print(f"[+] 已删除: {file_path}")
                except Exception as e:
                    print(f"[!] 删除失败 {file_path}: {e}")
    
    print(f"[+] 共删除 {pyc_count} 个.pyc文件和 {pycache_count} 个__pycache__目录")


def clean_all():
    """删除所有缓存和输出目录"""
    project_root = Path(__file__).parent
    
    # 需要删除的目录列表
    cleanup_dirs = [
        "cache",
        "icons_input", 
        "icons_zip",
        "localization/extra",
        "localization/output", 
        "localization/raw",
        "output",
        "sde_jsonl",
        "sde_jsonl_zip",
        "custom_icons"
    ]
    
    print("[+] 开始清理所有缓存和输出目录...")
    print("=" * 50)
    
    for dir_name in cleanup_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                print(f"[+] 已删除目录: {dir_name}")
            except Exception as e:
                print(f"[!] 删除目录失败 {dir_name}: {e}")
        else:
            print(f"[+] 目录不存在，跳过: {dir_name}")
    
    print("=" * 50)
    print("[+] 清理完成！")


if __name__ == "__main__":
    # 清理目录
    clean_all()
    # 清理Python缓存
    clean_python_cache()

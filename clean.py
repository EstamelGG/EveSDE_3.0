#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理脚本
删除缓存与可再生构建产出，用于全部重新构造。
不删除已跟踪的 output/whats_new、output/item_detail、history。
"""

import shutil
import os
from pathlib import Path


def clean_python_cache():
    """清理 Python 缓存文件"""
    print("[+] 清理Python缓存文件...")

    pyc_count = 0
    pycache_count = 0

    for root, dirs, files in os.walk("."):
        if "__pycache__" in dirs:
            cache_path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_path)
                pycache_count += 1
                print(f"[+] 已删除: {cache_path}")
            except Exception as e:
                print(f"[!] 删除失败 {cache_path}: {e}")

        for file in files:
            if file.endswith(".pyc"):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    pyc_count += 1
                    print(f"[+] 已删除: {file_path}")
                except Exception as e:
                    print(f"[!] 删除失败 {file_path}: {e}")

    print(f"[+] 共删除 {pyc_count} 个.pyc文件和 {pycache_count} 个__pycache__目录")


def clean_all():
    """删除 cache 与可再生 output 子目录"""
    project_root = Path(__file__).parent

    cleanup_dirs = [
        "cache",
        "output/sde",
        "output/icons",
        "output/release",
        "dist",
        "dist-ci.tar.gz",
        # 迁移前遗留目录
        "client_cache",
        "custom_icons",
        "icons_input",
        "icons_zip",
        "sde_jsonl",
        "sde_jsonl_zip",
        "output_sde",
        "output_icons",
        "temp_whats_new",
        "tmp",
    ]

    print("[+] 开始清理缓存和输出目录...")
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
    print("[+] 清理完成！（保留 output/whats_new、output/item_detail、history）")


if __name__ == "__main__":
    clean_all()
    clean_python_cache()

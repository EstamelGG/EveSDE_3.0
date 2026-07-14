#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVE SDE 处理器 - 主入口
参数 → 门闩/准备 → run_pipeline → 收尾
"""

import argparse
import os
import sys
from pathlib import Path

from evesde.brackets.parse_brackets_standalone import main as parse_brackets_main
from evesde.build_prep import (
    check_existing_version,
    check_network_connectivity,
    ensure_directories,
    get_latest_sde_info,
    load_config,
    process_localization,
    rebuild_output_directory,
    resolve_build_numbers,
    write_latest_log,
)
from evesde.pipeline import run_pipeline
from evesde.paths import PROJECT_ROOT
from evesde.utils.eve_client import EveClient, set_eve_client
from evesde.utils.single_db import get_db_path
import evesde.processors.sde_downloader as sde_downloader
import evesde.processors.version_info_processor as version_info_processor
import evesde.processors.compression_processor as compression_processor
import evesde.processors.release_compare_processor as release_compare_processor
import evesde.processors.item_detail_extractor as item_detail_extractor
import clean

os.environ["PYTHONUNBUFFERED"] = "1"


def parse_arguments():
    parser = argparse.ArgumentParser(description="EVE SDE 处理器")
    parser.add_argument("--force-localization", action="store_true", help="强制重新解析本地化数据")
    parser.add_argument("--skip-localization", action="store_true", help="跳过本地化数据解析")
    parser.add_argument("--force-rebuild", action="store_true", help="强制重新构建，忽略版本检查")
    parser.add_argument(
        "--skip-version-check",
        action="store_true",
        help="跳过版本一致性检查（允许 sde_binary 和 sde_update 版本号不一致）",
    )
    return parser.parse_args()


def safe_execute_processor(processor_func, processor_name, config):
    try:
        print(f"\n[+] 开始处理{processor_name}")
        result = processor_func(config)
        if result is not None and not result:
            print(f"[x] {processor_name}处理失败，程序退出")
            sys.exit(1)
        print(f"[+] {processor_name}处理完成")
        return True
    except Exception as e:
        print(f"[x] {processor_name}处理时发生异常: {e}")
        print("[x] 程序退出")
        sys.exit(1)


def main():
    args = parse_arguments()
    print("[+] EVE SDE 处理器启动")

    # --- 门闩：配置与版本 ---
    config = load_config()
    if not config:
        print("[x] 无法加载配置文件，程序退出")
        sys.exit(1)
    print("[+] 配置加载完成")
    print(f"[+] 支持语言: {', '.join(config.get('languages', ['en']))}")

    print("\n[+] 第一步: SDE版本检查")
    print("=" * 30)
    latest_sde_info = get_latest_sde_info(config, skip_version_check=args.skip_version_check)
    if not latest_sde_info:
        print("[x] 无法获取最新SDE版本信息，程序退出")
        sys.exit(1)

    current_release_date = latest_sde_info["release_date"]
    ccp_build_number, display_build_number, patch_version = resolve_build_numbers(latest_sde_info)

    if display_build_number != ccp_build_number:
        print(f"[+] 当前最新SDE版本: {ccp_build_number}")
        print(f"[+] 最终构建版本: {display_build_number}")
        print(f"[+] 补丁版本: {patch_version}")
    else:
        print(f"[+] 当前最新SDE版本: {ccp_build_number}")
        print(f"[+] 发布时间: {current_release_date}")

    config["sde_build_number"] = ccp_build_number

    if not args.force_rebuild:
        existing = check_existing_version()
        if existing and str(existing) == str(display_build_number):
            print(f"[+] 检测到相同版本 ({display_build_number})，跳过重新构建")
            print("[+] 如需强制重建，请使用 --force-rebuild 参数或删除 'output/latest.log' 文件")
            return

    # --- 准备 ---
    print("=" * 30)
    print("[+] 准备构造")
    clean.clean_python_cache()

    print("\n[+] 第二步: 网络连接检查")
    print("=" * 30)
    if not check_network_connectivity():
        print("[x] 网络连接检查失败，程序退出")
        sys.exit(1)

    print("\n[+] 第三步: 重构输出目录")
    print("=" * 30)
    rebuild_output_directory(config)
    ensure_directories(config)

    try:
        eve_client = EveClient.from_tq(
            PROJECT_ROOT / config["paths"].get("client_cache", "cache/client")
        )
        set_eve_client(eve_client)
        config["eve_client"] = eve_client
    except Exception as e:
        print(f"[x] EVE 客户端资源索引初始化失败: {e}")
        sys.exit(1)

    if not args.skip_localization:
        print("\n[+] 第四步: 处理本地化数据")
        print("=" * 30)
        if not process_localization(force=args.force_localization, eve_client=config["eve_client"]):
            print("[x] 本地化数据处理失败，程序退出")
            sys.exit(1)
        print("[+] 本地化数据处理完成")
    else:
        print("\n[+] 跳过本地化数据处理")

    print("\n[+] 开始执行SDE下载")
    if not sde_downloader.main(config, build_number=ccp_build_number):
        print("[x] SDE下载或解压失败，程序退出")
        print("[!] 请检查网络连接或重试")
        sys.exit(1)
    print("[+] SDE数据准备完成，继续后续处理...")

    print("\n[+] 生成 brackets_output.json")
    print("=" * 30)
    parse_brackets_main(eve_client=config.get("eve_client"))

    # --- 流水线 ---
    def on_step(_stage, name, fn):
        safe_execute_processor(fn, name, config)

    try:
        run_pipeline(config, on_step=on_step)
    except RuntimeError as e:
        print(f"[x] {e}")
        sys.exit(1)

    # --- 收尾 ---
    print("\n[+] 处理版本信息")
    print("=" * 30)
    if not version_info_processor.main(
        config,
        build_number=display_build_number,
        release_date=current_release_date,
        build_key=latest_sde_info.get("key"),
    ):
        print("[x] 版本信息处理失败，程序退出")
        sys.exit(1)
    print("[+] 版本信息处理完成")

    print("\n[+] 执行图标打包处理")
    print("=" * 30)
    safe_execute_processor(compression_processor.main, "图标打包", config)

    print("\n[+] 执行Release比较")
    print("=" * 30)
    if release_compare_processor.main(config, display_build_number):
        print("[+] Release比较完成")
    else:
        print("[!] Release比较失败，但继续执行")

    print("\n[+] 写入版本日志")
    print("=" * 30)
    write_latest_log(display_build_number, current_release_date)

    print("\n[+] 执行物品详细信息提取")
    print("=" * 30)
    db_path = get_db_path(config)
    print("[+] 提取英文版物品详细信息")
    en_ok = item_detail_extractor.item_detail_extract(str(db_path), "output/item_detail/en", lang="en")
    print("[+] 提取中文版物品详细信息")
    zh_ok = item_detail_extractor.item_detail_extract(str(db_path), "output/item_detail/zh", lang="zh")
    if en_ok and zh_ok:
        print("[+] 物品详细信息提取完成")
    else:
        print("[!] 物品详细信息提取部分失败")

    print("\n[+] 所有处理完成")


if __name__ == "__main__":
    main()

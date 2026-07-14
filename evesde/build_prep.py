#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建准备与门闩：配置、版本、网络、目录、本地化（不改业务输出）。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from evesde.paths import PROJECT_ROOT, ensure_dirs
from evesde.utils.http_client import get, create_session


def load_config() -> Optional[Dict[str, Any]]:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        print("[x] 配置文件不存在: config.json")
        return None
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[x] 配置文件格式错误: {e}")
        return None
    except Exception as e:
        print(f"[x] 加载配置文件失败: {e}")
        return None


def get_latest_sde_info(config: Dict[str, Any], skip_version_check: bool = False) -> Optional[Dict[str, Any]]:
    try:
        print("[+] 获取最新SDE版本信息...")
        sde_binary_url = config["urls"]["sde_binary"]
        sde_update_url = config["urls"]["sde_update"]

        print(f"[+] 从 sde_binary 获取版本信息: {sde_binary_url}")
        binary_response = get(sde_binary_url, timeout=10)
        binary_data = json.loads(binary_response.text.strip())
        binary_build_number = binary_data.get("build_number", binary_data.get("buildNumber", 0))
        if not binary_build_number:
            print("[x] sde_binary 响应中未找到 build_number")
            return None
        print(f"[+] sde_binary build_number: {binary_build_number}")

        print(f"[+] 从 sde_update 获取版本信息: {sde_update_url}")
        update_response = get(sde_update_url, timeout=10)
        update_data = json.loads(update_response.text.strip())
        update_build_number = update_data.get("buildNumber", update_data.get("build_number", 0))
        if not update_build_number:
            print("[x] sde_update 响应中未找到 buildNumber")
            return None
        print(f"[+] sde_update buildNumber: {update_build_number}")

        binary_build_str = str(binary_build_number)
        update_build_str = str(update_build_number)
        if binary_build_str != update_build_str:
            print("[!] 版本号不一致！")
            print(f"[!] sde_binary build_number: {binary_build_number}")
            print(f"[!] sde_update buildNumber: {update_build_number}")
            if skip_version_check:
                print(f"[!] 已跳过版本一致性检查，使用 sde_update 版本号: {update_build_number}")
            else:
                print("[x] 数据尚未同步完成，程序退出")
                print("[!] 如需强制构建，请使用 --skip-version-check 参数")
                return None
        else:
            print(f"[+] 版本号一致: {binary_build_number}")

        return {
            "build_number": update_build_number,
            "release_date": update_data.get("releaseDate"),
            "key": update_data.get("_key"),
        }
    except KeyError as e:
        print(f"[x] 配置文件中缺少必要的URL配置: {e}")
        return None
    except Exception as e:
        print(f"[x] 获取SDE版本信息失败: {e}")
        return None


def resolve_build_numbers(latest_sde_info: Dict[str, Any]) -> tuple:
    """返回 (ccp_build_number, display_build_number, patch_version)。"""
    import os

    current_build_number = latest_sde_info["build_number"]
    ccp_build_number = str(current_build_number).split(".", 1)[0]
    final_build_number = os.environ.get("FINAL_BUILD_NUMBER") or ccp_build_number
    patch_version = os.environ.get("PATCH_VERSION", "0")
    return ccp_build_number, final_build_number, patch_version


def check_existing_version() -> Optional[Any]:
    latest_log_path = PROJECT_ROOT / "output" / "sde" / "latest.log"
    if not latest_log_path.exists():
        return None
    try:
        with latest_log_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("build_number", data.get("buildNumber"))
    except Exception as e:
        print(f"[x] 读取现有版本信息失败: {e}")
        return None


def write_latest_log(build_number, release_date) -> None:
    sde_output_dir = PROJECT_ROOT / "output/sde"
    sde_output_dir.mkdir(exist_ok=True)
    latest_log_path = sde_output_dir / "latest.log"
    log_data = {
        "completion_time": datetime.now().isoformat(),
        "build_number": build_number,
        "release_date": release_date,
    }
    try:
        with latest_log_path.open("w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        print(f"[+] 已写入版本日志: {latest_log_path}")
    except Exception as e:
        print(f"[x] 写入版本日志失败: {e}")


def check_network_connectivity() -> bool:
    print("[+] 开始网络连接检查...")
    test_urls = [
        "https://images.evetech.net/corporations/500001/logo",
        "https://binaries.eveonline.com/eveclient_TQ.json",
        "https://esi.evetech.net/status",
    ]
    failed_urls = []
    session = create_session(default_timeout=10, verify=False)
    for url in test_urls:
        try:
            print(f"[+] 检查URL: {url}")
            response = session.head(url, allow_redirects=True)
            if response.status_code == 200:
                print(f"[+] URL可访问: {url}")
            else:
                print(f"[-] URL不可访问: {url} (状态码: {response.status_code})")
                failed_urls.append(url)
        except Exception as e:
            print(f"[x] 请求失败: {url} - {str(e)}")
            failed_urls.append(url)
    session.close()
    if failed_urls:
        print("\n[x] 网络检查失败，以下URL无法访问:")
        for url in failed_urls:
            print(f"    - {url}")
        print("\n[!] 请检查网络连接或稍后重试")
        print("[!] 如果问题持续存在，可能是服务器维护或SSL证书问题")
        return False
    print("\n[+] 网络检查完成，所有关键URL都可以正常访问")
    return True


def check_localization_exists() -> bool:
    localization_output = PROJECT_ROOT / "cache" / "localization" / "output"
    sde_localization_output = PROJECT_ROOT / "output" / "sde" / "localization"
    for file_name in ("en_multi_lang_mapping.json", "combined_localization.json"):
        if not (localization_output / file_name).exists():
            return False
    return (sde_localization_output / "accountingentrytypes_localized.json").exists()


def process_localization(force: bool = False, eve_client=None) -> bool:
    if not force and check_localization_exists():
        print("[+] 本地化数据已存在，跳过解析")
        return True
    print("[+] 开始处理本地化数据...")
    try:
        from evesde.localization.main import main as localization_main
        return localization_main(eve_client=eve_client)
    except Exception as e:
        print(f"[x] 调用本地化处理函数时出错: {e}")
        return False


def rebuild_output_directory(config: Dict[str, Any]) -> None:
    for rel in ("output/sde", "output/icons"):
        path = PROJECT_ROOT / rel
        if path.exists():
            print(f"[+] 清理输出目录: {path}")
            shutil.rmtree(path)


def ensure_directories(config: Dict[str, Any]) -> None:
    ensure_dirs(config)
    sde_localization_dir = PROJECT_ROOT / "output" / "sde" / "localization"
    sde_localization_dir.mkdir(parents=True, exist_ok=True)
    print(f"[+] 确保目录存在: {sde_localization_dir}")

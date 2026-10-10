#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建准备与门闩：配置、版本、网络、目录、本地化（不改业务输出）。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from typing import Any, Dict, Optional

from evesde.paths import PROJECT_ROOT, ensure_dirs, path
from evesde.utils.http_client import get


class SdeVersionMismatch(RuntimeError):
    """sde_binary 与 sde_update 版本号不一致：数据尚未同步完成，本次构建应跳过而非失败。"""

    def __init__(self, info: Dict[str, Any]):
        super().__init__(
            f"SDE 版本不一致：sde_binary={info['binary_build_number']}, sde_update={info['build_number']}"
        )
        self.info = info


def fetch_latest_sde_info(config: Dict[str, Any], skip_version_check: bool = False) -> Optional[Dict[str, Any]]:
    """查询最新 SDE 版本信息；版本不一致且未跳过检查时抛出 SdeVersionMismatch。"""
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
                print("[!] 数据尚未同步完成，本次构建跳过")
                print("[!] 如需强制构建，请使用 --skip-version-check 参数")
                raise SdeVersionMismatch({
                    "build_number": update_build_number,
                    "release_date": update_data.get("releaseDate"),
                    "key": update_data.get("_key"),
                    "client_data": binary_data,
                    "binary_build_number": binary_build_number,
                })
        else:
            print(f"[+] 版本号一致: {binary_build_number}")

        return {
            "build_number": update_build_number,
            "release_date": update_data.get("releaseDate"),
            "key": update_data.get("_key"),
            "client_data": binary_data,
        }
    except SdeVersionMismatch:
        raise
    except KeyError as e:
        print(f"[x] 配置文件中缺少必要的URL配置: {e}")
        return None
    except Exception as e:
        print(f"[x] 获取SDE版本信息失败: {e}")
        return None


def get_latest_sde_info(config: Dict[str, Any], skip_version_check: bool = False) -> Optional[Dict[str, Any]]:
    """开发入口使用：版本不一致时返回 None，由调用方提前结束。"""
    try:
        return fetch_latest_sde_info(config, skip_version_check=skip_version_check)
    except SdeVersionMismatch:
        return None


def write_latest_log(build_number, release_date, config) -> None:
    destination = path("sde_output", config) / "latest.log"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({
        "completion_time": datetime.now().isoformat(),
        "build_number": build_number,
        "release_date": release_date,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def rebuild_output_directory(config: Dict[str, Any]) -> None:
    """每次从空的可再生输出开始；已跟踪的历史和详情由对应阶段管理。"""
    for key in ("sde_output", "icons_output", "release_output"):
        target = path(key, config)
        if target == PROJECT_ROOT or PROJECT_ROOT not in target.parents:
            raise ValueError(f"构建输出必须位于项目子目录: {target}")
        if target.exists():
            shutil.rmtree(target)


def ensure_directories(config: Dict[str, Any]) -> None:
    ensure_dirs(config)
    (path("sde_output", config) / "localization").mkdir(parents=True, exist_ok=True)

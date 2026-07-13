#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将最终制品复制到 dist/（不在 .gitignore），供 CI artifact / release 使用。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

from evesde.paths import PROJECT_ROOT


def stage_dist(config: Dict[str, Any]) -> Path:
    """从 output/ 复制固定路径制品到 dist/。缺失必选文件则抛错。"""
    paths = config["paths"]
    dist = PROJECT_ROOT / paths["dist"]
    icons_src = PROJECT_ROOT / paths["icons_output"] / "icons.zip"
    sde_src = PROJECT_ROOT / paths["sde_output"]

    if not icons_src.is_file():
        raise FileNotFoundError(f"缺少必选制品: {icons_src}")
    if not (sde_src / "db" / "item_db.sqlite").is_file():
        raise FileNotFoundError(f"缺少必选制品: {sde_src / 'db' / 'item_db.sqlite'}")

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    shutil.copy2(icons_src, dist / "icons.zip")
    shutil.copytree(sde_src, dist / "sde")

    # 可选：CI 回写用
    for src_key, dest_name in (
        ("item_detail_en", "item_detail/en"),
        ("item_detail_zh", "item_detail/zh"),
        ("whats_new", "whats_new"),
    ):
        src = PROJECT_ROOT / paths[src_key]
        if src.exists():
            dest = dist / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)

    release_src = PROJECT_ROOT / paths.get("release_output", "output/release")
    if release_src.is_dir():
        for md in release_src.glob("release_compare_*.md"):
            shutil.copy2(md, dist / md.name)

    print(f"[+] 已暂存制品到 {dist}")
    print(f"    icons.zip: {(dist / 'icons.zip').stat().st_size} bytes")
    print(f"    sde/: {sum(1 for _ in (dist / 'sde').rglob('*') if _.is_file())} files")
    return dist


def main(config: Dict[str, Any] | None = None) -> bool:
    if config is None:
        import json
        with (PROJECT_ROOT / "config.json").open("r", encoding="utf-8") as f:
            config = json.load(f)
    stage_dist(config)
    return True

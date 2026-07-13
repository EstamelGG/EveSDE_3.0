#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 config.json 解析仓库内路径。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def path(key: str, config: Dict[str, Any] | None = None) -> Path:
    """返回 config['paths'][key] 相对仓库根的绝对 Path。"""
    cfg = config if config is not None else load_config()
    raw = cfg["paths"][key]
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def ensure_dirs(config: Dict[str, Any] | None = None) -> None:
    """创建主要 cache/output 目录。"""
    cfg = config if config is not None else load_config()
    for key in cfg.get("paths", {}):
        p = path(key, cfg)
        # 带后缀的视为文件路径，只保证父目录存在
        if p.suffix:
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)

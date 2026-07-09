#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单库路径：全语言合并为 item_db.sqlite。"""

from pathlib import Path
from typing import Any, Dict

DEFAULT_DB_NAME = "item_db.sqlite"


def get_db_path(config: Dict[str, Any]) -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / config["paths"]["db_output"] / DEFAULT_DB_NAME

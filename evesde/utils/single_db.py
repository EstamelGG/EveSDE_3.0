#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单库路径：全语言合并为 item_db.sqlite。"""

from evesde.paths import PROJECT_ROOT
from pathlib import Path
from typing import Any, Dict

DEFAULT_DB_NAME = "item_db.sqlite"


def get_db_path(config: Dict[str, Any]) -> Path:
    root = PROJECT_ROOT
    return root / config["paths"]["db_output"] / DEFAULT_DB_NAME

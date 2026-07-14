#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单库路径：全语言合并为 item_db.sqlite。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from evesde.paths import PROJECT_ROOT

DEFAULT_DB_NAME = "item_db.sqlite"


def get_db_path(config: Dict[str, Any]) -> Path:
    return PROJECT_ROOT / config["paths"]["db_output"] / DEFAULT_DB_NAME


@contextmanager
def open_item_db(config: Dict[str, Any], *, mkdir: bool = True) -> Iterator[sqlite3.Connection]:
    """连接 item_db：正常退出时 commit，始终 close。"""
    db_file = get_db_path(config)
    if mkdir:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

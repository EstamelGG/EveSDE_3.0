#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物品详细信息提取器冒烟测试。"""

from pathlib import Path
from evesde.processors.item_detail_extractor import ItemDetailExtractor
from evesde.paths import PROJECT_ROOT, path, load_config


def main():
    cfg = load_config()
    db_path = PROJECT_ROOT / cfg["paths"]["db_output"] / "item_db.sqlite"
    if not db_path.exists():
        print(f"[!] 数据库不存在: {db_path}")
        return

    out = PROJECT_ROOT / "tmp" / "item_detail_test"
    extractor = ItemDetailExtractor(str(db_path), str(out), lang="zh")
    data = extractor.get_item_detail(587)
    print("ok" if data else "fail", data.get("name") if data else None)


if __name__ == "__main__":
    main()

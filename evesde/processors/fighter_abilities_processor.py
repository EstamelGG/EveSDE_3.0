#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 fighterAbilities 与 fighterAbilitiesByType，写入 fighterAbilities 表。"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import LANGS, NAME_COLS, TOOLTIP_COLS, names_ddl, names_row, wide_texts
import sqlite3
from typing import Any, Dict, List, Tuple
import evesde.processors.jsonl_loader as jsonl_loader

SLOT_KEYS = ("abilitySlot0", "abilitySlot1", "abilitySlot2")


class FighterAbilitiesProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sde_jsonl_path = PROJECT_ROOT / config["paths"]["sde_input"]

    def _load_map(self, filename: str) -> Dict[int, Dict]:
        rows = jsonl_loader.load_jsonl(str(self.sde_jsonl_path / filename))
        return {item["_key"]: item for item in rows if "_key" in item}

    def create_table(self, cursor: sqlite3.Cursor):
        tooltip_ddl = ",\n                ".join(f"{c} TEXT" for c in TOOLTIP_COLS)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS fighterAbilities (
                type_id INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                ability_id INTEGER NOT NULL,
                cooldown_seconds INTEGER,
                charge_count INTEGER,
                rearm_time_seconds INTEGER,
                iconID INTEGER,
                target_mode TEXT,
                disallow_in_high_sec BOOLEAN,
                disallow_in_low_sec BOOLEAN,
                turret_graphic_id INTEGER,
                {names_ddl()},
                {tooltip_ddl},
                PRIMARY KEY (type_id, slot)
            ) WITHOUT ROWID
        ''')
        print("[+] 创建fighterAbilities表")

    def build_rows(self, abilities: Dict[int, Dict], by_type: Dict[int, Dict]) -> List[Tuple]:
        rows = []
        for type_id, type_data in by_type.items():
            for slot, key in enumerate(SLOT_KEYS):
                slot_data = type_data.get(key)
                if not slot_data:
                    continue
                ability_id = slot_data.get("abilityID")
                ability = abilities.get(ability_id, {})
                charges = slot_data.get("charges") or {}
                rows.append((
                    type_id,
                    slot,
                    ability_id,
                    slot_data.get("cooldownSeconds"),
                    charges.get("chargeCount"),
                    charges.get("rearmTimeSeconds"),
                    ability.get("iconID"),
                    ability.get("targetMode"),
                    1 if ability.get("disallowInHighSec") else 0,
                    1 if ability.get("disallowInLowSec") else 0,
                    ability.get("turretGraphicID"),
                    *names_row(wide_texts(ability.get("displayName"))),
                    *names_row(wide_texts(ability.get("tooltipText"))),
                ))
        return rows

    def process(self) -> bool:
        print("[+] 开始处理战斗机技能数据")
        abilities = self._load_map("fighterAbilities.jsonl")
        by_type = self._load_map("fighterAbilitiesByType.jsonl")
        if not abilities or not by_type:
            print("[x] 无法读取 fighterAbilities / fighterAbilitiesByType")
            return False

        db_path = get_db_path(self.config)
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS fighterAbilities")
            self.create_table(cursor)
            rows = self.build_rows(abilities, by_type)
            cols = (
                "type_id, slot, ability_id, cooldown_seconds, charge_count, rearm_time_seconds, "
                "iconID, target_mode, disallow_in_high_sec, disallow_in_low_sec, turret_graphic_id, "
                + ", ".join(NAME_COLS) + ", " + ", ".join(TOOLTIP_COLS)
            )
            placeholders = ", ".join(["?"] * (11 + len(LANGS) * 2))
            cursor.executemany(
                f"INSERT INTO fighterAbilities ({cols}) VALUES ({placeholders})",
                rows,
            )
            conn.commit()
            print(f"[+] fighterAbilities 写入 {len(rows)} 条 (技能定义 {len(abilities)}, 战斗机 {len(by_type)})")
            return True
        except Exception as e:
            print(f"[x] 处理战斗机技能数据时出错: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()


def main(config=None):
    print("[+] 战斗机技能数据处理器启动")
    if config is None:
        import json
        with open(PROJECT_ROOT / "config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    ok = FighterAbilitiesProcessor(config).process()
    print("\n[+] 战斗机技能数据处理器完成")
    return ok


if __name__ == "__main__":
    main()

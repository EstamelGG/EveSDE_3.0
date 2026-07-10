#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""类型特性处理器：traits 表使用 de_content / en_content 等宽列。"""

from utils.single_db import get_db_path
from utils.wide_i18n import LANGS, contents_ddl, contents_row, CONTENT_COLS
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
import scripts.jsonl_loader as jsonl_loader


class TypeTraitsProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.type_bonus_data = {}

    def load_type_bonus_data(self):
        print("[+] 加载类型加成数据...")
        type_bonus_file = self.sde_input_path / "typeBonus.jsonl"
        if not type_bonus_file.exists():
            print(f"[x] 文件不存在: {type_bonus_file}")
            return
        type_bonus_list = jsonl_loader.load_jsonl(str(type_bonus_file))
        self.type_bonus_data = {item['_key']: item for item in type_bonus_list}
        print(f"[+] 加载了 {len(self.type_bonus_data)} 个类型加成")

    def _bonus_content(self, bonus: Dict[str, Any], lang: str) -> str:
        bonus_text = bonus.get('bonusText')
        if not isinstance(bonus_text, dict):
            return ""
        content = bonus_text.get(lang) or bonus_text.get('en') or ""
        if not content:
            return ""
        if 'bonus' in bonus and 'unitID' in bonus:
            value = bonus['bonus']
            bonus_num = int(value) if isinstance(value, int) or float(value).is_integer() else round(float(value), 2)
            unit_id = bonus['unitID']
            if unit_id == 105:
                prefix = f"<b>{bonus_num}%</b> "
            elif unit_id == 104:
                prefix = f"<b>{bonus_num}x</b> "
            elif unit_id == 139:
                prefix = f"<b>{bonus_num}+</b> "
            else:
                prefix = f"<b>{bonus_num}</b> "
            content = prefix + content
        return content

    def _bonus_contents(self, bonus: Dict[str, Any]) -> Dict[str, str]:
        return {lang: self._bonus_content(bonus, lang) for lang in LANGS}

    def process_single_data(self, type_id: int, traits_data: Dict[str, Any]) -> List[Tuple]:
        rows = []

        def add(skill: int, bonus_type: str, bonus: Dict[str, Any]):
            contents = self._bonus_contents(bonus)
            if not any(contents.values()):
                return
            rows.append((
                type_id, skill, bonus.get('importance', 999999), bonus_type, *contents_row(contents),
            ))

        for bonus in traits_data.get('roleBonuses', []):
            add(-1, 'roleBonuses', bonus)

        for skill_bonus in traits_data.get('types', []):
            skill_id = skill_bonus['_key']
            for bonus in skill_bonus.get('_value', []):
                add(skill_id, 'typeBonuses', bonus)

        for bonus in traits_data.get('miscBonuses', []):
            add(-1, 'miscBonuses', bonus)

        return sorted(rows, key=lambda x: x[2])

    def create_traits_table(self, cursor: sqlite3.Cursor):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS traits (
                typeid INTEGER NOT NULL,
                skill INTEGER NOT NULL DEFAULT -1,
                importance INTEGER,
                bonus_type TEXT,
                {contents_ddl()},
                PRIMARY KEY (typeid, skill, bonus_type, importance)
            ) WITHOUT ROWID
        ''')

    def process_traits_to_db(self, cursor: sqlite3.Cursor):
        print("[+] 开始处理traits数据...")
        self.create_traits_table(cursor)
        cursor.execute('DELETE FROM traits')

        content_cols = ", ".join(CONTENT_COLS)
        insert_sql = f'''
            INSERT OR REPLACE INTO traits
            (typeid, skill, importance, bonus_type, {content_cols})
            VALUES (?, ?, ?, ?, {", ".join(["?"] * 8)})
        '''
        batch = []
        batch_size = 500
        for type_id, type_data in self.type_bonus_data.items():
            for row in self.process_single_data(type_id, type_data):
                batch.append(row)
                if len(batch) >= batch_size:
                    cursor.executemany(insert_sql, batch)
                    batch = []
        if batch:
            cursor.executemany(insert_sql, batch)

        cursor.execute('SELECT COUNT(*) FROM traits')
        print(f"[+] traits数据处理完成: {cursor.fetchone()[0]} 个")

    def update_all_databases(self, config):
        self.load_type_bonus_data()
        db_file = get_db_path(config)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n[+] 处理数据库: {db_file}")
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            self.process_traits_to_db(cursor)
            conn.commit()
            conn.close()
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")


def main(config=None):
    print("[+] 类型特性处理器启动")
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    processor = TypeTraitsProcessor(config)
    processor.update_all_databases(config)
    print("\n[+] 类型特性处理器完成")


if __name__ == "__main__":
    main()

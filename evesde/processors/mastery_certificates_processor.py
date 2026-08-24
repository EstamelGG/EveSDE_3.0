#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专精认证处理器：certificates / certificateSkills / masteries 三张表。

- certificates：认证主表（多语名称/描述）
- certificateSkills：认证各等级技能要求（basic/standard/improved/advanced/elite = 认证1-5级）
- masteries：物品专精等级所需认证（masteryLevel 1-5）
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import NAME_COLS, DESC_COLS, names_ddl, descs_ddl, wide_texts, names_row
import sqlite3
from typing import Dict, Any, List, Tuple
import evesde.processors.jsonl_loader as jsonl_loader

# 认证等级 1-5 对应的档位名
CERT_LEVELS = ("basic", "standard", "improved", "advanced", "elite")

BATCH_SIZE = 500


class MasteryCertificatesProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.certificates: List[Dict[str, Any]] = []
        self.masteries: List[Dict[str, Any]] = []

    def load_data(self):
        cert_file = self.sde_input_path / "certificates.jsonl"
        self.certificates = jsonl_loader.load_jsonl(str(cert_file)) if cert_file.exists() else []
        print(f"[+] 加载了 {len(self.certificates)} 个认证")

        mastery_file = self.sde_input_path / "masteries.jsonl"
        self.masteries = jsonl_loader.load_jsonl(str(mastery_file)) if mastery_file.exists() else []
        print(f"[+] 加载了 {len(self.masteries)} 个物品专精")

    def create_tables(self, cursor: sqlite3.Cursor):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS certificates (
                certificateID INTEGER NOT NULL PRIMARY KEY,
                groupID INTEGER,
                {names_ddl()},
                {descs_ddl()}
            ) WITHOUT ROWID
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certificateSkills (
                certificateID INTEGER NOT NULL,
                skillID INTEGER NOT NULL,
                basic INTEGER NOT NULL DEFAULT 0,
                standard INTEGER NOT NULL DEFAULT 0,
                improved INTEGER NOT NULL DEFAULT 0,
                advanced INTEGER NOT NULL DEFAULT 0,
                elite INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (certificateID, skillID)
            ) WITHOUT ROWID
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS masteries (
                typeid INTEGER NOT NULL,
                masteryLevel INTEGER NOT NULL,
                certificateID INTEGER NOT NULL,
                PRIMARY KEY (typeid, masteryLevel, certificateID)
            ) WITHOUT ROWID
        ''')

    @staticmethod
    def _batch_insert(cursor: sqlite3.Cursor, sql: str, rows: List[Tuple]):
        batch = []
        for row in rows:
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                cursor.executemany(sql, batch)
                batch = []
        if batch:
            cursor.executemany(sql, batch)

    def certificate_rows(self) -> List[Tuple]:
        rows = []
        for cert in self.certificates:
            cert_id = cert["_key"]
            names = names_row(wide_texts(cert.get("name")))
            descs = names_row(wide_texts(cert.get("description")))
            rows.append((cert_id, cert.get("groupID"), *names, *descs))
        return rows

    def certificate_skill_rows(self) -> List[Tuple]:
        rows = []
        for cert in self.certificates:
            cert_id = cert["_key"]
            for skill in cert.get("skillTypes", []):
                skill_id = skill["_key"]
                levels = tuple(int(skill.get(level) or 0) for level in CERT_LEVELS)
                rows.append((cert_id, skill_id, *levels))
        return rows

    def mastery_rows(self) -> List[Tuple]:
        rows = []
        for entry in self.masteries:
            type_id = entry["_key"]
            for level in entry.get("_value", []):
                mastery_level = level["_key"] + 1  # key 0-4 -> 等级 1-5
                for cert_id in level.get("_value", []):
                    rows.append((type_id, mastery_level, cert_id))
        return rows

    def process_to_db(self, cursor: sqlite3.Cursor):
        print("[+] 开始处理专精认证数据...")
        self.create_tables(cursor)

        cursor.execute('DELETE FROM certificates')
        self._batch_insert(cursor, f'''
            INSERT OR REPLACE INTO certificates
            (certificateID, groupID, {", ".join(NAME_COLS)}, {", ".join(DESC_COLS)})
            VALUES (?, ?, {", ".join(["?"] * 16)})
        ''', self.certificate_rows())

        cursor.execute('DELETE FROM certificateSkills')
        self._batch_insert(cursor, f'''
            INSERT OR REPLACE INTO certificateSkills
            (certificateID, skillID, {", ".join(CERT_LEVELS)})
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', self.certificate_skill_rows())

        cursor.execute('DELETE FROM masteries')
        self._batch_insert(cursor, '''
            INSERT OR REPLACE INTO masteries (typeid, masteryLevel, certificateID)
            VALUES (?, ?, ?)
        ''', self.mastery_rows())

        for table in ("certificates", "certificateSkills", "masteries"):
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            print(f"[+] {table}: {cursor.fetchone()[0]} 行")

    def update_database(self, config):
        self.load_data()
        db_file = get_db_path(config)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n[+] 处理数据库: {db_file}")
        conn = sqlite3.connect(str(db_file))
        try:
            cursor = conn.cursor()
            self.process_to_db(cursor)
            conn.commit()
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")
            raise
        finally:
            conn.close()


def main(config=None):
    print("[+] 专精认证处理器启动")
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    processor = MasteryCertificatesProcessor(config)
    processor.update_database(config)
    print("\n[+] 专精认证处理器完成")


if __name__ == "__main__":
    main()

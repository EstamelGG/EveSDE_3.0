#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能需求数据处理器模块
"""

from utils.single_db import get_db_path
from utils.wide_i18n import LANGS, names_row, names_ddl, name_cols_sql
import sqlite3
from pathlib import Path
from typing import Dict, Any


class SkillRequirementsProcessor:
    """技能需求数据处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])

    def create_skill_requirements_table(self, cursor: sqlite3.Cursor):
        type_cols = name_cols_sql("type")
        category_cols = name_cols_sql("category")
        type_cols_fmt = type_cols.replace(", ", ",\n            ")
        category_cols_fmt = category_cols.replace(", ", ",\n            ")
        cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS typeSkillRequirement (
            typeid INTEGER NOT NULL,
            typeicon TEXT,
            published BOOLEAN,
            categoryID INTEGER,
            {type_cols_fmt},
            {category_cols_fmt},
            required_skill_id INTEGER NOT NULL,
            required_skill_level INTEGER,
            PRIMARY KEY (typeid, required_skill_id)
        ) WITHOUT ROWID
        ''')
        print("[+] 创建typeSkillRequirement表")

    def process_skill_requirements_to_db(self, cursor: sqlite3.Cursor):
        try:
            self.create_skill_requirements_table(cursor)
            cursor.execute('DELETE FROM typeSkillRequirement')

            skill_requirements = [
                (182, 277), (183, 278), (184, 279),
                (1285, 1286), (1289, 1287), (1290, 1288),
            ]

            type_name_cols = ", ".join(f"type_{lang}_name" for lang in LANGS)
            category_name_cols = ", ".join(f"category_{lang}_name" for lang in LANGS)
            cursor.execute(f'''
                SELECT type_id, icon_filename, published, categoryID,
                       {", ".join(f"{lang}_name" for lang in LANGS)},
                       {", ".join(f"category_{lang}_name" for lang in LANGS)}
                FROM types
            ''')
            items = cursor.fetchall()

            print(f"[+] 开始处理技能需求数据，共 {len(items)} 个物品")
            processed_count = 0
            insert_sql = f'''
                INSERT OR REPLACE INTO typeSkillRequirement
                (typeid, typeicon, published, categoryID,
                 {type_name_cols}, {category_name_cols},
                 required_skill_id, required_skill_level)
                VALUES (?, ?, ?, ?, {", ".join(["?"] * 16)}, ?, ?)
            '''

            for item in items:
                type_id = item[0]
                type_icon, published, category_id = item[1:4]
                type_names = item[4:12]
                category_names = item[12:20]

                for skill_attr_id, level_attr_id in skill_requirements:
                    cursor.execute('''
                        SELECT value FROM typeAttributes
                        WHERE type_id = ? AND attribute_id = ?
                    ''', (type_id, skill_attr_id))
                    skill_result = cursor.fetchone()
                    if not skill_result:
                        continue

                    required_skill_id = int(float(skill_result[0]))
                    cursor.execute('''
                        SELECT value FROM typeAttributes
                        WHERE type_id = ? AND attribute_id = ?
                    ''', (type_id, level_attr_id))
                    level_result = cursor.fetchone()
                    if not level_result:
                        continue

                    required_level = int(float(level_result[0]))
                    cursor.execute(insert_sql, (
                        type_id, type_icon, published, category_id,
                        *type_names, *category_names,
                        required_skill_id, required_level,
                    ))
                    processed_count += 1

            print(f"[+] 技能需求数据处理完成，共处理 {processed_count} 个技能需求")

        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise

    def process_skill_requirements_for_language(self, language: str) -> bool:
        db_path = get_db_path(self.config)
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            self.process_skill_requirements_to_db(cursor)
            conn.commit()
            return True
        except Exception as e:
            print(f"[x] 处理技能需求数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def process_all_languages(self) -> bool:
        print("[+] 开始处理技能需求数据")
        return self.process_skill_requirements_for_language('en')


def main(config=None):
    print("[+] 技能需求数据处理器启动")
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    processor = SkillRequirementsProcessor(config)
    processor.process_all_languages()
    print("\n[+] 技能需求数据处理器完成")


if __name__ == "__main__":
    main()

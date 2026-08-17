#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设施装配效果数据处理器模块
用于处理设施装配效果数据并写入数据库

功能: 从官方 SDE 读取工业修正源与目标过滤器，处理设施装配效果
数据源:
- industryModifierSources.jsonl
- industryTargetFilters.jsonl
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
import sqlite3
from typing import Dict, List, Tuple, Any
import evesde.processors.jsonl_loader as jsonl_loader


class FacilityRigEffectsProcessor:
    """设施装配效果数据处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_input"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self._modifier_data = None
        self._filter_data = None

    def _load_jsonl_map(self, filename: str) -> Dict[int, Dict]:
        jsonl_file = self.sde_jsonl_path / filename
        rows = jsonl_loader.load_jsonl(str(jsonl_file))
        return {item["_key"]: item for item in rows if "_key" in item}

    def create_facility_rig_effects_table(self, cursor: sqlite3.Cursor):
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facility_rig_effects (
            id INTEGER NOT NULL,
            category INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            PRIMARY KEY (id, category, group_id)
        ) WITHOUT ROWID
        ''')
        print("[+] 创建facility_rig_effects表")

    def process_industry_modifier_sources(
        self,
        modifier_data: Dict,
        filter_data: Dict,
        cursor: sqlite3.Cursor,
    ) -> List[Tuple]:
        facility_effects = []

        for facility_id, facility_data in modifier_data.items():
            cursor.execute(
                '''
                SELECT marketGroupID FROM types
                WHERE type_id = ? AND marketGroupID IS NOT NULL
                ''',
                (facility_id,),
            )
            if not cursor.fetchone():
                continue

            for activity_type in ("manufacturing", "reaction"):
                if activity_type not in facility_data:
                    continue
                activity_data = facility_data[activity_type]

                material_filter_dogma_map = {}
                time_filter_dogma_map = {}
                for material in activity_data.get("material", []):
                    if "dogmaAttributeID" in material:
                        material_filter_dogma_map[material.get("filterID")] = material["dogmaAttributeID"]
                for time_item in activity_data.get("time", []):
                    if "dogmaAttributeID" in time_item:
                        time_filter_dogma_map[time_item.get("filterID")] = time_item["dogmaAttributeID"]

                for filter_id in set(material_filter_dogma_map) | set(time_filter_dogma_map):
                    if filter_id is None:
                        facility_effects.append((facility_id, 0, 0))
                        continue
                    filter_info = filter_data.get(filter_id)
                    if not filter_info:
                        continue
                    if "categoryIDs" in filter_info:
                        for category_id in filter_info["categoryIDs"]:
                            facility_effects.append((facility_id, category_id, 0))
                    if "groupIDs" in filter_info:
                        for group_id in filter_info["groupIDs"]:
                            facility_effects.append((facility_id, 0, group_id))
                    if "categoryIDs" not in filter_info and "groupIDs" not in filter_info:
                        facility_effects.append((facility_id, 0, 0))

        return facility_effects

    def insert_facility_rig_effects(self, cursor: sqlite3.Cursor, effects_data: List[Tuple]):
        cursor.execute("DELETE FROM facility_rig_effects")
        cursor.executemany(
            '''
            INSERT OR REPLACE INTO facility_rig_effects
            (id, category, group_id)
            VALUES (?, ?, ?)
            ''',
            effects_data,
        )

    def process_facility_rig_effects_to_db(self, cursor: sqlite3.Cursor, lang: str):
        try:
            if self._modifier_data is None:
                print("[+] 读取官方 SDE 工业修正数据...")
                self._modifier_data = self._load_jsonl_map("industryModifierSources.jsonl")
                self._filter_data = self._load_jsonl_map("industryTargetFilters.jsonl")
                if not self._modifier_data or not self._filter_data:
                    raise RuntimeError("无法读取 industryModifierSources / industryTargetFilters")
                print(f"[+] 修正源数据: {len(self._modifier_data)} 个设施")
                print(f"[+] 目标过滤器: {len(self._filter_data)} 个过滤器")

            self.create_facility_rig_effects_table(cursor)
            effects_data = self.process_industry_modifier_sources(
                self._modifier_data, self._filter_data, cursor
            )
            self.insert_facility_rig_effects(cursor, effects_data)

            cursor.execute("SELECT COUNT(*) FROM facility_rig_effects")
            total_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT id) FROM facility_rig_effects")
            facility_count = cursor.fetchone()[0]
            print(f"[+] 语言 {lang}: 总记录数 {total_count}, 设施数量 {facility_count}")
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise

    def process_facility_rig_effects_for_language(self, language: str) -> bool:
        print(f"[+] 开始处理设施装配效果数据，语言: {language}")
        db_path = get_db_path(self.config)
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            self.process_facility_rig_effects_to_db(cursor, language)
            conn.commit()
            print(f"[+] 设施装配效果数据处理完成，语言: {language}")
            return True
        except Exception as e:
            print(f"[x] 处理设施装配效果数据时出错: {e}")
            return False
        finally:
            if "conn" in locals():
                conn.close()

    def process_all_languages(self) -> bool:
        print("[+] 开始处理设施装配效果数据")
        return self.process_facility_rig_effects_for_language("en")


def main(config=None):
    print("[+] 设施装配效果数据处理器启动")
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    processor = FacilityRigEffectsProcessor(config)
    ok = processor.process_all_languages()
    print("\n[+] 设施装配效果数据处理器完成")
    return ok


if __name__ == "__main__":
    main()

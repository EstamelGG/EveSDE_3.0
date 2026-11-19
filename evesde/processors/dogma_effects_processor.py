#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dogma效果处理器模块
处理EVE Dogma效果数据并存储到数据库
包括效果、属性分类、属性单位等信息
"""

from evesde.paths import load_config, PROJECT_ROOT
from evesde.utils.single_db import get_db_path, open_item_db
from evesde.utils.wide_i18n import wide_texts, names_row
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import evesde.processors.jsonl_loader as jsonl_loader


_MODIFIER_DOMAINS = {
    "shipID", "itemID", "charID", "otherID",
    "structureID", "targetID", "target",
}
_MODIFIER_FUNCS = {
    "ItemModifier", "LocationModifier", "LocationGroupModifier",
    "LocationRequiredSkillModifier", "OwnerRequiredSkillModifier",
    "EffectStopper",
}
_MODIFIER_OPERATIONS = {-1, 0, 1, 2, 3, 4, 5, 6, 7, 9}


def canonical_modifier_info(modifier_info: Any) -> str:
    """Canonical JSON used for comparing the official and patched definitions."""
    return json.dumps(
        modifier_info,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def modifier_info_sha256(modifier_info: Any) -> str:
    return hashlib.sha256(
        canonical_modifier_info(modifier_info).encode("utf-8")
    ).hexdigest()


def load_effect_patches(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Dogma effect patch file is missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        patches = json.load(f)
    if not isinstance(patches, list) or not patches:
        raise ValueError(f"Dogma effect patch file must be a non-empty list: {path}")
    return patches


def _validate_reference(
    cursor: sqlite3.Cursor,
    table: str,
    column: str,
    value: int,
    label: str,
    effect_name: str,
) -> None:
    cursor.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (value,))
    if cursor.fetchone() is None:
        raise ValueError(
            f"{effect_name}: unknown {label} {value} referenced by patch"
        )


def validate_effect_patches(
    cursor: sqlite3.Cursor,
    patches: List[Dict[str, Any]],
) -> None:
    """Validate every patch before changing the database."""
    for index, patch in enumerate(patches):
        label = f"dogma_effect_patches[{index}]"
        if not isinstance(patch, dict):
            raise ValueError(f"{label}: patch must be an object")

        effect_id = patch.get("effect_id")
        effect_name = patch.get("effect_name")
        expected_hash = patch.get("expected_modifier_info_sha256")
        modifier_info = patch.get("modifier_info")

        if not isinstance(effect_id, int) or effect_id <= 0:
            raise ValueError(f"{label}: effect_id must be a positive integer")
        if not isinstance(effect_name, str) or not effect_name:
            raise ValueError(f"{label}: effect_name must be a non-empty string")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(
                f"{label}: expected_modifier_info_sha256 must be a SHA-256 hex string"
            )
        if not isinstance(modifier_info, list) or not modifier_info:
            raise ValueError(f"{label}: modifier_info must be a non-empty list")

        cursor.execute(
            "SELECT modifier_info FROM dogmaEffects "
            "WHERE effect_id = ? AND effect_name = ?",
            (effect_id, effect_name),
        )
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise ValueError(
                f"{effect_name}({effect_id}): patch must match exactly one "
                f"dogmaEffects row, matched {len(rows)}"
            )

        raw_modifier_info = rows[0][0]
        try:
            actual_modifier_info = (
                json.loads(raw_modifier_info)
                if raw_modifier_info is not None
                else None
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{effect_name}({effect_id}): official modifier_info is invalid JSON"
            ) from exc

        actual_hash = modifier_info_sha256(actual_modifier_info)
        if actual_hash != expected_hash:
            raise ValueError(
                f"{effect_name}({effect_id}): official modifier_info changed. "
                f"expected {expected_hash}, got {actual_hash}. "
                "Review the SDE change and update the patch deliberately."
            )

        for modifier in modifier_info:
            if not isinstance(modifier, dict):
                raise ValueError(
                    f"{effect_name}({effect_id}): each modifier must be an object"
                )
            missing = {
                "domain", "func", "operation",
                "modifiedAttributeID", "modifyingAttributeID",
            } - modifier.keys()
            if missing:
                raise ValueError(
                    f"{effect_name}({effect_id}): modifier misses "
                    f"{', '.join(sorted(missing))}"
                )

            domain = modifier["domain"]
            func = modifier["func"]
            operation = modifier["operation"]
            modified_id = modifier["modifiedAttributeID"]
            modifying_id = modifier["modifyingAttributeID"]

            if domain not in _MODIFIER_DOMAINS:
                raise ValueError(
                    f"{effect_name}({effect_id}): unknown modifier domain {domain!r}"
                )
            if func not in _MODIFIER_FUNCS:
                raise ValueError(
                    f"{effect_name}({effect_id}): unknown modifier func {func!r}"
                )
            if operation not in _MODIFIER_OPERATIONS:
                raise ValueError(
                    f"{effect_name}({effect_id}): unknown modifier operation {operation!r}"
                )
            if not isinstance(modified_id, int) or not isinstance(modifying_id, int):
                raise ValueError(
                    f"{effect_name}({effect_id}): modifier attribute IDs must be integers"
                )

            _validate_reference(
                cursor, "dogmaAttributes", "attribute_id", modified_id,
                "modified attribute", effect_name,
            )
            _validate_reference(
                cursor, "dogmaAttributes", "attribute_id", modifying_id,
                "modifying attribute", effect_name,
            )

            group_id = modifier.get("groupID", 0)
            if group_id:
                _validate_reference(
                    cursor, "groups", "group_id", group_id,
                    "group", effect_name,
                )

            skill_type_id = modifier.get("skillTypeID", 0)
            if skill_type_id and skill_type_id != -1:
                _validate_reference(
                    cursor, "types", "type_id", skill_type_id,
                    "skill type", effect_name,
                )


class DogmaEffectsProcessor:
    """EVE Dogma效果处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Dogma效果处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.dogma_effects_data = {}
    
    def load_dogma_effects_data(self):
        """加载Dogma效果数据"""
        print("[+] 加载Dogma效果数据...")
        
        # 加载Dogma效果数据
        effects_file = self.sde_input_path / "dogmaEffects.jsonl"
        effects_list = jsonl_loader.load_jsonl(str(effects_file))
        self.dogma_effects_data = {item['_key']: item for item in effects_list}
        print(f"[+] 加载了 {len(self.dogma_effects_data)} 个Dogma效果")
    
    def create_dogma_effects_table(self, cursor: sqlite3.Cursor):
        """创建dogmaEffects表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dogmaEffects (
                effect_id INTEGER NOT NULL PRIMARY KEY,
                effect_category INTEGER,
                effect_name TEXT,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                de_description TEXT,
                en_description TEXT,
                es_description TEXT,
                fr_description TEXT,
                ja_description TEXT,
                ko_description TEXT,
                ru_description TEXT,
                zh_description TEXT,
                published BOOLEAN,
                is_assistance BOOLEAN,
                is_offensive BOOLEAN,
                resistance_attribute_id INTEGER,
                modifier_info TEXT
            )
        ''')
    
    
    def process_dogma_effects_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理Dogma效果数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理Dogma效果数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_dogma_effects_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM dogmaEffects')
        
        # 处理Dogma效果数据
        effects_batch = []
        batch_size = 1000
        
        _fx_sql = '''
            INSERT OR REPLACE INTO dogmaEffects (
                effect_id, effect_category, effect_name,
                de_name, en_name, es_name, fr_name,
                ja_name, ko_name, ru_name, zh_name,
                de_description, en_description, es_description, fr_description,
                ja_description, ko_description, ru_description, zh_description,
                published, is_assistance, is_offensive, resistance_attribute_id, modifier_info
            ) VALUES ({ph})
        '''.format(ph=", ".join(["?"] * 24))

        for effect_id, effect_data in self.dogma_effects_data.items():
            # 获取基本字段
            effect_name = effect_data['name']
            if isinstance(effect_name, dict):
                effect_name = effect_name.get('en', '')

            displays = wide_texts(effect_data.get('displayName'))
            descs = wide_texts(effect_data.get('description'))
            
            # 效果分类特殊处理
            if effect_name == "online":  # 打补丁修复
                effect_category = 4
            else:
                effect_category = effect_data['effectCategoryID']
            
            published = effect_data.get('published', False)
            is_assistance = effect_data.get('isAssistance', False)
            is_offensive = effect_data.get('isOffensive', False)
            resistance_attribute_id = effect_data.get('resistanceAttributeID', None)
            
            # 处理modifierInfo字段，转换为JSON字符串
            modifier_info = effect_data.get('modifierInfo', None)
            modifier_info_json = json.dumps(modifier_info) if modifier_info is not None else None
            
            # 多语言字段处理
            effects_batch.append((
                effect_id, effect_category, effect_name,
                *names_row(displays), *names_row(descs),
                published, is_assistance, is_offensive, resistance_attribute_id, modifier_info_json
            ))
            
            # 批量插入
            if len(effects_batch) >= batch_size:
                cursor.executemany(_fx_sql, effects_batch)
                effects_batch = []

        if effects_batch:
            cursor.executemany(_fx_sql, effects_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM dogmaEffects')
        effects_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] Dogma效果数据处理完成:")
        print(f"    - 效果: {effects_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config) -> bool:
        """更新所有语言的数据库"""
        project_root = PROJECT_ROOT
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载Dogma效果数据
        self.load_dogma_effects_data()
        
        db_file = get_db_path(config)
        print(f"\n[+] 处理数据库: {db_file}")
        try:
            with open_item_db(config) as conn:
                cursor = conn.cursor()
                self.process_dogma_effects_to_db(cursor, 'en')
                self._apply_effect_patches(cursor)
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")
            raise
        return True

    def _apply_effect_patches(
        self,
        cursor: sqlite3.Cursor,
        patch_path: Path | None = None,
    ) -> None:
        """应用 data/dogma_effect_patches.json（原独立回填步骤）。"""
        patch_path = patch_path or (
            PROJECT_ROOT / "data" / "dogma_effect_patches.json"
        )
        patches = load_effect_patches(patch_path)
        validate_effect_patches(cursor, patches)

        for patch in patches:
            effect_id = patch["effect_id"]
            effect_name = patch["effect_name"]
            modifier_info = json.dumps(patch["modifier_info"], separators=(",", ":"))
            cursor.execute(
                "UPDATE dogmaEffects SET modifier_info = ? "
                "WHERE effect_id = ? AND effect_name = ?",
                (modifier_info, effect_id, effect_name),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    f"{effect_name}({effect_id}): expected one updated row, "
                    f"updated {cursor.rowcount}"
                )
            print(f"[+] dogmaEffects 已修补 {effect_name}({effect_id})")
        print(f"[+] dogmaEffects 共应用 {len(patches)} 条受控补丁")


def main(config=None):
    """主函数"""
    print("[+] Dogma效果处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        config = load_config()
    
    # 创建处理器并执行
    processor = DogmaEffectsProcessor(config)
    success = processor.update_all_databases(config)

    if success:
        print("\n[+] Dogma效果处理器完成")
    else:
        print("\n[x] Dogma效果处理器失败")
    return success


if __name__ == "__main__":
    main()

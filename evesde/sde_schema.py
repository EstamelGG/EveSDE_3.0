#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SDE JSONL 输入契约校验。

这里只声明流水线真正依赖的文件和字段。字段缺失属于上游 schema 破坏，
必须让构建失败，不能像可选业务数据那样静默生成空表。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, Optional, Tuple

from evesde.paths import path


class SdeSchemaError(RuntimeError):
    """SDE 文件缺失、为空或缺少流水线必需字段。"""


# 每个文件至少在前若干条记录中必须出现的字段。当前 SDE 已确认这些字段
# 对所有记录都成立；稀疏字段（如 packagedVolume、position2D）不在此处声明。
JSONL_FIELD_CONTRACTS: Dict[str, Tuple[str, ...]] = {
    "accountingEntryTypes.jsonl": ("_key", "internalName", "name"),
    "agentsInSpace.jsonl": ("_key", "solarSystemID"),
    "blueprints.jsonl": ("_key", "activities", "maxProductionLimit"),
    "categories.jsonl": ("_key", "name"),
    "certificates.jsonl": ("_key", "name", "skillTypes"),
    "compressibleTypes.jsonl": ("_key", "compressedTypeID"),
    "dbuffCollections.jsonl": ("_key",),
    "dogmaAttributeCategories.jsonl": ("_key", "name"),
    "dogmaAttributes.jsonl": ("_key", "name"),
    "dogmaEffects.jsonl": ("_key", "name", "effectCategoryID"),
    "dogmaUnits.jsonl": ("_key",),
    "dynamicItemAttributes.jsonl": ("_key", "attributeIDs"),
    "factions.jsonl": ("_key", "name"),
    "fighterAbilities.jsonl": ("_key", "displayName"),
    "fighterAbilitiesByType.jsonl": ("_key",),
    "graphics.jsonl": ("_key",),
    "groups.jsonl": ("_key", "name", "categoryID"),
    "icons.jsonl": ("_key", "iconFile"),
    "industryModifierSources.jsonl": ("_key",),
    "industryTargetFilters.jsonl": ("_key",),
    "mapConstellations.jsonl": ("_key", "name", "regionID"),
    "mapMoons.jsonl": ("_key", "solarSystemID"),
    "mapPlanets.jsonl": ("_key", "solarSystemID"),
    "mapRegions.jsonl": ("_key", "name"),
    "mapSolarSystems.jsonl": ("_key", "name", "regionID"),
    "mapStargates.jsonl": ("_key", "solarSystemID", "destination"),
    "mapStars.jsonl": ("_key",),
    "marketGroups.jsonl": ("_key", "name"),
    "masteries.jsonl": ("_key", "_value"),
    "metaGroups.jsonl": ("_key", "name"),
    "npcCharacters.jsonl": ("_key", "name"),
    "npcCorporationDivisions.jsonl": ("_key", "name"),
    "npcCorporations.jsonl": ("_key", "name"),
    "npcStations.jsonl": ("_key", "solarSystemID", "operationID"),
    "planetSchematics.jsonl": ("_key", "name", "pins", "types"),
    "skinLicenses.jsonl": ("_key", "skinID"),
    "skinMaterials.jsonl": ("_key", "materialSetID"),
    "skins.jsonl": ("_key", "skinMaterialID"),
    "stationOperations.jsonl": ("_key", "operationName"),
    "typeBonus.jsonl": ("_key",),
    "typeDogma.jsonl": ("_key",),
    "typeMaterials.jsonl": ("_key",),
    "types.jsonl": ("_key", "name", "groupID"),
}

# 小文件全量校验；大文件校验前 N 条，避免为校验再完整解析数百 MB 数据。
FULL_VALIDATION_FILES = {"blueprints.jsonl"}
SCHEMA_SAMPLE_SIZE = 200


BLUEPRINT_ACTIVITIES = (
    "copying",
    "manufacturing",
    "research_material",
    "research_time",
    "invention",
    "reaction",
)


def validate_blueprint_record(record: Dict, filename: str, line_number: int) -> None:
    """校验蓝图活动结构；活动内部的字段同样属于构建契约。"""
    activities = record.get("activities")
    if not isinstance(activities, dict) or not activities:
        raise SdeSchemaError(
            f"SDE schema 不兼容: {filename} 第 {line_number} 行 activities 为空或不是对象"
        )

    for activity_name in BLUEPRINT_ACTIVITIES:
        if activity_name not in activities:
            continue
        activity = activities[activity_name]
        if not isinstance(activity, dict):
            raise SdeSchemaError(
                f"SDE schema 不兼容: {filename} 第 {line_number} 行 "
                f"activity {activity_name} 不是对象"
            )
        if "time" not in activity:
            raise SdeSchemaError(
                f"SDE schema 不兼容: {filename} 第 {line_number} 行 "
                f"activity {activity_name} 缺少字段 time"
            )
        for list_name in ("materials", "products", "skills"):
            if list_name not in activity:
                continue
            items = activity[list_name]
            if not isinstance(items, list):
                raise SdeSchemaError(
                    f"SDE schema 不兼容: {filename} 第 {line_number} 行 "
                    f"activity {activity_name}.{list_name} 不是列表"
                )
            required = ("typeID", "level") if list_name == "skills" else ("typeID", "quantity")
            for item in items:
                if not isinstance(item, dict):
                    raise SdeSchemaError(
                        f"SDE schema 不兼容: {filename} 第 {line_number} 行 "
                        f"activity {activity_name}.{list_name} 含非对象记录"
                    )
                missing = [field for field in required if field not in item]
                if missing:
                    raise SdeSchemaError(
                        f"SDE schema 不兼容: {filename} 第 {line_number} 行 "
                        f"activity {activity_name}.{list_name} 缺少字段 "
                        f"{', '.join(missing)}"
                    )


def validate_jsonl_file(
    file_path: Path,
    required_fields: Iterable[str],
    *,
    validate_all: bool = False,
    sample_size: int = SCHEMA_SAMPLE_SIZE,
    record_validator: Optional[Callable[[Dict, str, int], None]] = None,
) -> int:
    """校验一个 JSONL 文件，返回已检查的非空记录数。"""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise SdeSchemaError(f"SDE 必需文件不存在: {file_path}")

    required = tuple(required_fields)
    checked = 0
    try:
        with file_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                if not validate_all and checked >= sample_size:
                    break
                checked += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SdeSchemaError(
                        f"SDE 文件 {file_path.name} 第 {line_number} 行不是合法 JSON: {exc}"
                    ) from exc
                if not isinstance(record, dict):
                    raise SdeSchemaError(
                        f"SDE 文件 {file_path.name} 第 {line_number} 行不是 JSON 对象"
                    )
                missing = [field for field in required if field not in record]
                if missing:
                    key = record.get("_key", "?")
                    raise SdeSchemaError(
                        f"SDE schema 不兼容: {file_path.name} 第 {line_number} 行 "
                        f"(_key={key}) 缺少字段 {', '.join(missing)}"
                    )
                if record_validator is not None:
                    record_validator(record, file_path.name, line_number)
    except OSError as exc:
        raise SdeSchemaError(f"无法读取 SDE 文件 {file_path}: {exc}") from exc

    if checked == 0:
        raise SdeSchemaError(f"SDE 必需文件为空: {file_path.name}")
    return checked


def validate_sde_directory(
    sde_dir: Path,
    contracts: Optional[Mapping[str, Iterable[str]]] = None,
) -> None:
    """校验构建所需的完整 SDE JSONL 契约。"""
    sde_dir = Path(sde_dir)
    if not sde_dir.is_dir():
        raise SdeSchemaError(f"SDE 输入目录不存在: {sde_dir}")

    selected = contracts if contracts is not None else JSONL_FIELD_CONTRACTS
    for filename, fields in selected.items():
        checked = validate_jsonl_file(
            sde_dir / filename,
            fields,
            validate_all=filename in FULL_VALIDATION_FILES,
            record_validator=validate_blueprint_record if filename == "blueprints.jsonl" else None,
        )
        print(f"[+] SDE schema 校验通过: {filename} ({checked} 条)")


def validate_input(config: Dict) -> bool:
    """流水线入口：校验当前构建实际使用的 SDE 解压目录。"""
    validate_sde_directory(path("sde_input", config))
    print("[+] SDE schema 校验完成")
    return True

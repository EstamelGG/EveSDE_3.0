"""物品级变更报告：new 为新增 ID，modify 为已有物品的稀疏差异。"""
import json

_MISSING = object()


def value_text(value):
    if value is _MISSING or value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def change(old=_MISSING, new=_MISSING):
    return {"old": value_text(old), "new": value_text(new)}


def material_values(materials):
    """按材料 ID 整理数量；重复记录保留，排序不影响比较。"""
    grouped = {}
    for material in materials:
        grouped.setdefault(str(material["typeID"]), []).append({"quantity": material["quantity"]})
    return {key: records[0] if len(records) == 1 else sorted(records, key=value_text)
            for key, records in grouped.items()}


def field_changes(old, new):
    """生成仅包含变化叶子的嵌套 KV 差异。"""
    if ((isinstance(old, dict) and new is not _MISSING and not isinstance(new, dict))
            or (isinstance(new, dict) and old is not _MISSING and not isinstance(old, dict))):
        return change(old, new)
    if isinstance(old, dict) or isinstance(new, dict):
        left = old if isinstance(old, dict) else {}
        right = new if isinstance(new, dict) else {}
        result = {}
        for key in sorted(left.keys() | right.keys()):
            difference = field_changes(left.get(key, _MISSING), right.get(key, _MISSING))
            if difference is not None:
                result[key] = difference
        return result or None
    return None if old == new else change(old, new)


def dogma_values(analyzer, type_id, *, old=False):
    source = analyzer.old_typedogma_data if old else analyzer.current_typedogma_data
    return {str(attr["attributeID"]): attr.get("value", 0)
            for attr in source.get(type_id, {}).get("dogmaAttributes", [])}


def blueprint_materials(blueprint):
    return {"activities": {
        activity: {"materials": material_values(data["materials"])}
        for activity, data in blueprint.get("activities", {}).items()
        if data.get("materials")
    }}


def build_report(analyzer):
    old_ids = set(analyzer.old_types_data)
    new_ids = set(analyzer.current_types_data)
    modified = {}
    for type_id in sorted(old_ids & new_ids, key=int):
        is_blueprint = (type_id in analyzer.old_blueprints_data
                        or type_id in analyzer.current_blueprints_data)
        changes = {}
        if is_blueprint:
            old = blueprint_materials(analyzer.old_blueprints_data.get(type_id, {}))
            new = blueprint_materials(analyzer.current_blueprints_data.get(type_id, {}))
            blueprint = field_changes(old, new)
            if blueprint:
                changes["blueprint"] = blueprint
        else:
            attributes = field_changes(dogma_values(analyzer, type_id, old=True),
                                       dogma_values(analyzer, type_id))
            if attributes:
                changes["attributes"] = attributes
        if changes:
            modified[type_id] = {"kind": "blueprint" if is_blueprint else "item", **changes}
    return {"new": sorted(map(int, new_ids - old_ids)), "modify": modified}

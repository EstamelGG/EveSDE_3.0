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


def normalize_blueprint(value, field=None):
    """材料、产品、技能从列表转为 typeID 映射，保留完整活动数据。"""
    if isinstance(value, dict):
        return {str(key): normalize_blueprint(item, key) for key, item in value.items()
                if key not in ("_key", "name", "displayName")}
    if isinstance(value, list) and field in ("materials", "products", "skills"):
        result = {}
        for item in value:
            key = str(item["typeID"])
            if key in result:
                raise ValueError(f"蓝图 {field} 中 typeID 重复: {key}")
            result[key] = normalize_blueprint({key: val for key, val in item.items() if key != "typeID"})
        return result
    return value


def field_changes(old, new):
    """生成嵌套 KV 差异；列表重排不产生材料/产品/技能的假变更。"""
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


def build_report(analyzer):
    old_ids = set(analyzer.old_types_data)
    new_ids = set(analyzer.current_types_data)
    modified = {}
    for type_id in sorted(old_ids & new_ids, key=int):
        attributes = field_changes(dogma_values(analyzer, type_id, old=True),
                                   dogma_values(analyzer, type_id))
        is_blueprint = (type_id in analyzer.old_blueprints_data
                        or type_id in analyzer.current_blueprints_data)
        changes = {}
        if attributes:
            changes["attributes"] = attributes
        if is_blueprint:
            old = normalize_blueprint(analyzer.old_blueprints_data.get(type_id, {}))
            new = normalize_blueprint(analyzer.current_blueprints_data.get(type_id, {}))
            # typeID 已是实体键，不把蓝图身份字段重复当作变化。
            old.pop("blueprintTypeID", None)
            new.pop("blueprintTypeID", None)
            blueprint = field_changes(old, new)
            if blueprint:
                changes["blueprint"] = blueprint
        if changes:
            modified[type_id] = {"kind": "blueprint" if is_blueprint else "item", **changes}
    return {"new": sorted(map(int, new_ids - old_ids)), "modify": modified}

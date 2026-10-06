"""whats_new JSON v1：实体 ID 为键，变更值为 old/new 文本，不包含显示名称。"""
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


def build_report(analyzer, new_items, ship_blueprints, blueprint_changes, attribute_changes,
                 icon_changes, *, old_version=None, new_version=None):
    items = {}
    for item in sorted(new_items, key=lambda item: item["type_id"]):
        type_id = item["type_id"]
        # JSON 保留 0 值；Markdown 可以继续省略新物品的零值属性。
        attributes = dogma_values(analyzer, type_id) if item["attributes"] is not None else {}
        items[type_id] = {
            "group_id": value_text(item["group_id"]),
            "category_id": value_text(item["category_id"]),
            "description": change(new=item["description"]),
            "attributes": {key: change(new=value) for key, value in sorted(attributes.items())},
        }
    ships = {}
    for type_id, blueprint in sorted(ship_blueprints.items()):
        ships[type_id] = {
            "blueprint_id": value_text(blueprint["blueprint_id"]),
            "materials": {str(item["typeID"]): change(new=item.get("quantity", 0))
                          for item in blueprint["materials"]},
        }
    blueprints = {}
    for status, records in blueprint_changes.items():
        for blueprint_id in sorted(records):
            old = normalize_blueprint(analyzer.old_blueprints_data.get(blueprint_id, {}))
            new = normalize_blueprint(analyzer.current_blueprints_data.get(blueprint_id, {}))
            differences = field_changes(old, new)
            if differences or status != "changed":
                blueprints[blueprint_id] = {"status": status, "changes": differences or {}}
    attributes = {}
    for type_id, item in sorted(attribute_changes.items()):
        old, new = dogma_values(analyzer, type_id, old=True), dogma_values(analyzer, type_id)
        attributes[type_id] = {
            attr["attributeID"]: change(old.get(attr["attributeID"], _MISSING), new.get(attr["attributeID"], _MISSING))
            for attr in sorted(item["changes"], key=lambda attr: attr["attributeID"])
        }
    old_icons, new_icons = analyzer.icon_hashes
    icons = {name: change(old_icons.get(name, _MISSING), new_icons.get(name, _MISSING))
             for name in sorted(set().union(*icon_changes.values()))}
    return {
        "schema_version": 1,
        "versions": {"old": old_version, "new": new_version},
        "new_items": items,
        "new_ships": ships,
        "blueprint_changes": blueprints,
        "attribute_changes": attributes,
        "icon_changes": icons,
    }

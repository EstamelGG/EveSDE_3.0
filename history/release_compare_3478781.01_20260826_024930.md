# EVE SDE Build 3478781.01 - 版本比较报告

**构建时间**: 2026-08-26 02:48:13

## 图标文件比较

本次更新未发现图标文件变更。

## 数据库比较

### 单库 (item_db.sqlite)

**数据库差异摘要**:
- 语句总数: 14
- INSERT: 0 / UPDATE: 13 / DELETE: 0 / 其他: 1

**按表统计**（差异）:

| 表 | INSERT | UPDATE | DELETE | 合计 |
|---|---|---|---|---|
| dynamic_item_attributes | 0 | 12 | 0 | 12 |
| version_info | 0 | 1 | 0 | 1 |

**差异样例**（前 14 行）:
```sql
ALTER TABLE dynamic_item_attributes ADD COLUMN high_is_good;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=47699 AND attribute_id=20;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=47700 AND attribute_id=20;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=47701 AND attribute_id=20;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=52228 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=52229 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=52231 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=85490 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=85492 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=1 WHERE type_id=85493 AND attribute_id=73;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=85557 AND attribute_id=20;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=85558 AND attribute_id=20;
UPDATE dynamic_item_attributes SET high_is_good=0 WHERE type_id=85559 AND attribute_id=20;
UPDATE version_info SET patch_number=1 WHERE id=1;
```

## 地图和本地化文件比较

### regions_data.json

文件无差异

### systems_data.json

文件无差异

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

文件无差异


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3478781.01.md**: 详细比较报告

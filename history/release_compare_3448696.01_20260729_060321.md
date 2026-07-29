# EVE SDE Build 3448696.01 - 版本比较报告

**构建时间**: 2026-07-29 06:01:56

## 图标文件比较

本次更新未发现图标文件变更。

## 数据库比较

### 单库 (item_db.sqlite)

**数据库差异摘要**:
- 语句总数: 1
- INSERT: 0 / UPDATE: 1 / DELETE: 0

**按表统计**（差异）:

| 表 | INSERT | UPDATE | DELETE | 合计 |
|---|---|---|---|---|
| version_info | 0 | 1 | 0 | 1 |

**差异样例**（前 1 行）:
```sql
UPDATE version_info SET patch_number=1 WHERE id=1;
```

## 地图和本地化文件比较

### regions_data.json

**文件差异**:
```diff
--- old_regions_data.json
+++ new_regions_data.json
@@ -3,8 +3,8 @@
     "region_id": 10000001,

     "faction_id": 500007,

     "center": {

-      "x": 529.8,

-      "y": 443.9

+      "x": 389.8,

+      "y": 475.0

     },

     "relations": [

       "10000011",

@@ -19,8 +19,8 @@
     "region_id": 10000002,

     "faction_id": 500001,

     "center": {

-      "x": 434.5,

-      "y": 669.5

+      "x": 374.7,

+      "y": 615.3

     },

     "relations": [

       "10000003",

@@ -37,8 +37,8 @@
     "region_id": 10000003,

     "faction_id": 0,

     "center": {

-      "x": 472.3,

-      "y": 756.8

+      "x": 416.2,

+      "y": 669.9

     },

     "relations": [

       "10000002",

@@ -51,8 +51,8 @@
     "region_id": 10000004,

     "faction_id": 0,

     "center": {

-      "x": 613.1,

-      "y": 873.3

+      "x": 522.4,

+      "y": 742.1

     },

     "relations": []

   },

@@ -60,8 +60,8 @@
     "region_id": 10000005,

     "faction_id": 0,

     "center": {

... (还有 722 行差异)
```

### systems_data.json

**文件差异**:
```diff
--- old_systems_data.json
+++ new_systems_data.json
@@ -3,8 +3,8 @@
     "region_id": 10000001,

     "faction_id": 500007,

     "center": {

-      "x": 529.8,

-      "y": 443.9

+      "x": 389.8,

+      "y": 475.0

     },

     "relations": [

       "10000011",

@@ -1041,8 +1041,8 @@
     "region_id": 10000002,

     "faction_id": 500001,

     "center": {

-      "x": 434.5,

-      "y": 669.5

+      "x": 374.7,

+      "y": 615.3

     },

     "relations": [

       "10000003",

@@ -1815,8 +1815,8 @@
     "region_id": 10000003,

     "faction_id": 0,

     "center": {

-      "x": 472.3,

-      "y": 756.8

+      "x": 416.2,

+      "y": 669.9

     },

     "relations": [

       "10000002",

@@ -2837,8 +2837,8 @@
     "region_id": 10000004,

     "faction_id": 0,

     "center": {

-      "x": 613.1,

-      "y": 873.3

+      "x": 522.4,

+      "y": 742.1

     },

     "relations": [],

     "systems": {

@@ -3336,8 +3336,8 @@
     "region_id": 10000005,

     "faction_id": 0,

     "center": {

... (还有 722 行差异)
```

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

文件无差异


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3448696.01.md**: 详细比较报告

# EVE SDE Build 3430261.01 - 版本比较报告

**构建时间**: 2026-07-13 08:33:49

## 图标文件比较

**文件统计**:
- 当前版本: 8371 个文件
- 旧版本: 8371 个文件
- 新增: 0 个文件
- 删除: 0 个文件
- 共同: 8371 个文件

## 数据库比较

### 单库 (item_db.sqlite)

**数据库差异摘要**:
- 语句总数: 1
- INSERT: 0 / UPDATE: 1 / DELETE: 0

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
@@ -1016,401 +1016,5 @@
     "relations": [

       "10000067"

     ]

-  },

-  {

-    "region_id": 11000001,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

-    "relations": []

-  },

-  {

-    "region_id": 11000002,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

-    "relations": []

-  },

-  {

-    "region_id": 11000003,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

-    "relations": []

-  },

-  {

-    "region_id": 11000004,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

-    "relations": []

-  },

-  {

-    "region_id": 11000005,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

... (还有 354 行差异)
```

### systems_data.json

**文件差异**:
```diff
--- old_systems_data.json
+++ new_systems_data.json
@@ -47005,12553 +47005,5 @@
         "30100083"

       ]

     }

-  },

-  "11000001": {

-    "region_id": 11000001,

-    "faction_id": 0,

-    "center": {

-      "x": 0.0,

-      "y": 0.0

-    },

-    "relations": [],

-    "systems": {

-      "31000007": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000008": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000009": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000010": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000011": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000012": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000013": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000014": {

-        "x": 0.0,

-        "y": 0.0

-      },

-      "31000015": {

-        "x": 0.0,

... (还有 12506 行差异)
```

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

文件无差异


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3430261.01.md**: 详细比较报告

# EVE SDE Build 3500372.01 - 版本比较报告

**构建时间**: 2026-09-10 09:05:09

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

文件无差异

### systems_data.json

文件无差异

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

**文件差异**:
```diff
--- /tmp/tmprhewogh0/sde_old/localization/accountingentrytypes_localized.json
+++ /home/runner/work/EveSDE_3.0/EveSDE_3.0/output/sde/localization/accountingentrytypes_localized.json
@@ -5917,6 +5917,32 @@
       "zh": [

         "提炼税"

       ]

+    },

+    "entryJournalMessage": {

+      "en": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "de": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "es": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "fr": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "ja": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "ko": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "ru": [

+        "Fee paid by {name1} for use of {name2} reprocessing facility"

+      ],

+      "zh": [

+        "{name1}向{name2}支付使用提炼设施的费用"

+      ]

     }

   },

   "jump_clone_activation_fee": {

```


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3500372.01.md**: 详细比较报告

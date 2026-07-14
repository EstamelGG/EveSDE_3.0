# EVE SDE Build 3430261.02 - 版本比较报告

**构建时间**: 2026-07-14 06:23:14

## 图标文件比较

**文件统计**:
- 当前版本: 8391 个文件
- 旧版本: 8371 个文件
- 新增: 20 个文件
- 删除: 0 个文件
- 共同: 8371 个文件

**新增文件** (20 个):
- `category_16.png`
- `category_17.png`
- `category_18.png`
- `category_2.png`
- `category_2100.png`
- `category_2143.png`
- `category_22.png`
- `category_23.png`
- `category_3.png`
- `category_34.png`
- `category_4.png`
- `category_40.png`
- `category_41.png`
- `category_46.png`
- `category_5.png`
- `category_63.png`
- `category_65.png`
- `category_66.png`
- `category_87.png`
- `category_9.png`

## 数据库比较

### 单库 (item_db.sqlite)

**数据库差异摘要**:
- 语句总数: 21
- INSERT: 0 / UPDATE: 21 / DELETE: 0

**差异样例**（前 21 行）:
```sql
UPDATE categories SET icon_filename='category_2.png' WHERE category_id=2;
UPDATE categories SET icon_filename='category_3.png' WHERE category_id=3;
UPDATE categories SET icon_filename='category_4.png' WHERE category_id=4;
UPDATE categories SET icon_filename='category_5.png' WHERE category_id=5;
UPDATE categories SET icon_filename='category_9.png' WHERE category_id=9;
UPDATE categories SET icon_filename='category_16.png' WHERE category_id=16;
UPDATE categories SET icon_filename='category_17.png' WHERE category_id=17;
UPDATE categories SET icon_filename='category_18.png' WHERE category_id=18;
UPDATE categories SET icon_filename='category_22.png' WHERE category_id=22;
UPDATE categories SET icon_filename='category_23.png' WHERE category_id=23;
UPDATE categories SET icon_filename='category_34.png' WHERE category_id=34;
UPDATE categories SET icon_filename='category_40.png' WHERE category_id=40;
UPDATE categories SET icon_filename='category_41.png' WHERE category_id=41;
UPDATE categories SET icon_filename='category_46.png' WHERE category_id=46;
UPDATE categories SET icon_filename='category_63.png' WHERE category_id=63;
UPDATE categories SET icon_filename='category_65.png' WHERE category_id=65;
UPDATE categories SET icon_filename='category_66.png' WHERE category_id=66;
UPDATE categories SET icon_filename='category_87.png' WHERE category_id=87;
UPDATE categories SET icon_filename='category_2100.png' WHERE category_id=2100;
UPDATE categories SET icon_filename='category_2143.png' WHERE category_id=2143;
UPDATE version_info SET patch_number=2 WHERE id=1;
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
- **release_compare_3430261.02.md**: 详细比较报告

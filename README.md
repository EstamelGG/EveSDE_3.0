# EVE SDE 2.0 处理器

EVE Online静态数据导出(SDE)的现代化处理工具，支持多语言本地化和完整的游戏数据处理。

## 主要特性

### 本地化数据处理
- **自动下载**: 从EVE在线服务器自动下载最新的本地化数据
- **多语言支持**: 支持9种语言的完整本地化（en, zh, de, es, fr, ja, ko, ru, it）
- **智能缓存**: 自动检测本地化数据是否存在，避免重复下载
- **参数控制**: 支持强制重新解析或跳过本地化处理

### 完整数据处理
- **SDE数据**: 处理EVE Online的所有静态数据
- **图标下载**: 自动下载和处理游戏图标
- **数据库生成**: 生成完整的SQLite数据库
- **模块化设计**: 每个数据类型独立处理，便于维护

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基本使用
```bash
# 自动处理所有数据（包括本地化）
python main.py

# 强制重新解析本地化数据
python main.py --force-localization

# 跳过本地化数据处理
python main.py --skip-localization
```

### 单独处理本地化数据
```bash
cd localization
python main.py
```

## 命令行参数

- `--force-localization`: 强制重新解析本地化数据
- `--skip-localization`: 跳过本地化数据解析

## 输出数据

- `output/db/item_db_en.sqlite.zip`: 英文sde数据库
- `output/db/item_db_zh.sqlite.zip`: 中文sde数据库
- `output/icons/icons.zip`: 图标包
- `output/localization/accountingentrytypes_localized.json`: 会计条目类型本地化
- `output/maps/regions_data.json`: (地图)星域位置数据
- `output/maps/systems_data.json`: (地图)星系位置数据
- `output/maps/neighbors_data.json`: (地图)邻居星系关系数据

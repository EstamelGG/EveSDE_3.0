# EVE SDE 3.0 处理器

EVE Online 静态数据导出 (SDE) 的现代化处理工具，支持多语言本地化和完整的游戏数据处理。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

常用参数：

- `--force-localization`: 强制重新解析本地化数据
- `--skip-localization`: 跳过本地化数据解析
- `--force-rebuild`: 强制重新构建，忽略版本检查

## 项目结构

```text
evesde/           # 主包
  processors/     # SDE 各处理器
  utils/          # 公共工具
  localization/   # 本地化代码
  icon_builder/   # 图标构建
  brackets/       # brackets 解析
cache/            # 运行时缓存（gitignore）
output/
  sde/            # DB / maps / texts.zip / localization
  icons/          # icons.zip
  item_detail/    # en、zh 物品详情（可提交）
  whats_new/      # 变更报告（可提交）
  release/        # CI 发布打包中间产物
data/             # 静态源数据
tools/            # 开发辅助工具
```

## 输出数据

- `output/sde/db/item_db.sqlite`: 单库全语言宽列
- `output/sde/texts.zip`: 长文本包
- `output/icons/icons.zip`: 图标包
- `output/sde/maps/`: 星图 JSON
- `output/sde/localization/`: 会计条目等本地化产物

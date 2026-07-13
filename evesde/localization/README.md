# EVE SDE 本地化数据提取器

这个工具用于从EVE Online客户端提取本地化数据，依照old版本的功能来创建本地化JSON文件。

## 功能特点

- **纯网络下载**: 仅从EVE在线服务器下载最新的资源文件
- **无需本地客户端**: 不依赖本地EVE客户端安装
- **多语言支持**: 支持9种语言的本地化数据提取
- **完整流程**: 包含数据提取、解包、合并和映射生成

## 支持的语言

- en (英语)
- zh (中文)
- de (德语)
- es (西班牙语)
- fr (法语)
- ja (日语)
- ko (韩语)
- ru (俄语)
- it (意大利语)

## 使用方法

### 1. 运行完整流程

```bash
cd localization
python main.py
```

这将执行完整的本地化数据提取流程：
1. 从网络下载resfileindex和本地化pickle文件
2. 解包pickle文件为JSON格式
3. 处理会计条目类型的本地化
4. 生成合并的本地化数据

### 2. 单独运行组件

#### 本地化数据提取器
```bash
python localization_extractor.py
```

#### 会计条目类型本地化器
```bash
python accounting_types_localizer.py
```

## 输出文件

运行完成后，在`output/`目录中会生成以下文件：

- `combined_localization.json`: 所有语言的合并本地化数据
- `en_multi_lang_mapping.json`: 英文到多种语言的映射
- `accountingentrytypes_localized.json`: 会计条目类型的本地化数据

## 数据来源

**仅从EVE在线服务器下载最新资源**:
- 获取最新的构建信息
- 下载resfileindex.txt文件
- 下载本地化pickle文件
- 无需本地EVE客户端安装

## 目录结构

```
localization/
├── main.py                          # 主控制脚本
├── localization_extractor.py        # 本地化数据提取器
├── accounting_types_localizer.py    # 会计条目类型本地化器
├── raw/                             # 原始pickle文件
├── extra/                           # 解包后的JSON文件
└── output/                          # 最终输出文件
```

## 依赖要求

- Python 3.7+
- requests>=2.31.0
- 网络连接（用于下载资源文件）

## 注意事项

1. 需要稳定的网络连接来下载资源文件
2. 下载的文件会缓存在`raw/`目录中，可以重复使用
3. 确保有足够的磁盘空间存储下载的文件

## 错误处理

- 网络连接失败时会显示相应的错误信息
- 所有错误都会在控制台中显示，便于调试
- 建议在网络状况良好时运行

## 与old版本的兼容性

这个工具完全兼容old版本的输出格式，生成的JSON文件可以直接用于新系统的本地化处理。

# EVE Online 图标生成器 - Python版本

这是EVE Online图标生成器的Python实现版本，与原Rust版本功能完全一致。

## 功能特性

- 自动获取和更新EVE Online静态数据导出(SDE)
- 智能处理不同类型的游戏物品图标
- 支持多种输出格式
- 高效的缓存机制避免重复下载
- 完整的日志和调试支持

## 安装依赖

### Python版本要求
- Python 3.10 或更高版本

### 安装依赖包
```bash
pip install -r requirements.txt
```

或使用pip3:
```bash
pip3 install -r requirements.txt
```

## 使用方法

### 基本语法
```bash
python main.py -u "你的用户代理" [选项] <子命令> [子命令选项]
```

### 全局选项
- `-u, --user_agent`: (必需) HTTP请求的用户代理字符串
- `-c, --cache_folder`: 游戏数据缓存文件夹 (默认: ./cache)
- `-i, --icon_folder`: 图标输出/缓存文件夹 (默认: ./icons)
- `-l, --logfile`: 日志文件路径
- `--append_log`: 追加到日志文件而非覆盖
- `--silent`: 静默模式
- `-f, --force_rebuild`: 强制重建未改变的图标
- `-s, --skip_if_fresh`: 如果图标未改变则跳过输出

### 子命令

#### 1. service_bundle - 服务包格式
生成包含所有图标和元数据的ZIP文件，适用于图标服务托管。

```bash
python main.py -u "Tritanium/1.0" service_bundle -o output.zip
```

忽略皮肤图标

```bash
python main.py -u "Tritanium/1.0" --skip_skins service_bundle -o ./output/output.zip
```

单项测试
```bash
python main.py -u "Tritanium/1.0" --test_type_id 47107 -f service_bundle -o ./output/test_47107.zip
```

#### 2. iec - 图像导出集合
生成标准化的图标导出集合ZIP文件。

```bash
python main.py -u "Tritanium/1.0" iec -o icons.zip
```

#### 3. web_dir - Web托管目录
准备用于Web托管的目录结构。

```bash
# 使用符号链接（默认）
python main.py -u "Tritanium/1.0" web_dir -o ./web

# 复制文件
python main.py -u "Tritanium/1.0" web_dir -o ./web --copy_files

# 使用硬链接
python main.py -u "Tritanium/1.0" web_dir -o ./web --hardlink
```

#### 4. checksum - 校验和
计算当前图标集的MD5校验和。

```bash
# 输出到stdout
python main.py -u "Tritanium/1.0" checksum

# 保存到文件
python main.py -u "Tritanium/1.0" checksum -o checksum.txt
```

#### 5. aux_icons - 辅助图标转储
转储所有原始图标文件。

```bash
python main.py -u "Tritanium/1.0" aux_icons -o aux_icons.zip
```

#### 6. aux_all - 所有图像转储
转储所有图像资源。

```bash
python main.py -u "Tritanium/1.0" aux_all -o all_images.zip
```

## 使用示例

### 生成服务包并记录日志
```bash
python main.py -u "Tritanium/1.0" -l build.log service_bundle -o icons_bundle.zip
```

### 强制重建所有图标
```bash
python main.py -u "Tritanium/1.0" -f service_bundle -o icons_bundle.zip
```

### 静默模式生成Web目录
```bash
python main.py -u "Tritanium/1.0" --silent web_dir -o ./web_icons --copy_files
```

## 输出格式说明

### Service Bundle
- 包含所有图标文件
- 包含`service_metadata.json`元数据文件
- 文件名使用哈希值确保唯一性

### IEC (Image Export Collection)
- 标准化的文件命名：`{type_id}_64.png`
- 蓝图副本：`{type_id}_bpc_64.png`
- 高分辨率渲染：`{type_id}_512.jpg`

### Web目录
- 每个物品类型有对应的JSON元数据文件
- 图标文件命名：`{type_id}_{kind}.{ext}`
- 包含`index.json`索引文件

## 技术说明

### 图标类型
- **icon**: 普通物品图标
- **bp**: 蓝图图标
- **bpc**: 蓝图副本图标
- **reaction**: 反应蓝图图标
- **relic**: 遗迹图标
- **render**: 高分辨率渲染图

### 特殊处理
- 自动添加技术等级标识
- 蓝图背景和覆盖层合成
- SKIN材质特殊处理
- 反应蓝图使用特殊背景

## 与Rust版本的差异

Python版本与Rust版本在以下方面保持一致：
- 输出文件内容完全相同
- 输出文件格式完全相同
- 命令行接口基本一致
- 处理逻辑完全一致

主要区别：
- 使用Python标准库和常用第三方库
- 不支持ImageMagick选项（仅使用Pillow）
- 性能可能略低于Rust版本

## 故障排除

### 网络连接问题
确保可以访问以下域名：
- `binaries.eveonline.com`
- `resources.eveonline.com`
- `developers.eveonline.com`

### 依赖问题
如果遇到依赖安装问题，请确保：
- Python版本 >= 3.10
- pip已更新到最新版本：`pip install --upgrade pip`

### 权限问题
在Windows上创建符号链接可能需要管理员权限，建议使用`--copy_files`或`--hardlink`选项。

## 许可证

与原项目保持一致。

## 贡献

欢迎提交问题报告和改进建议。

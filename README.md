# EVE SDE 3.0

面向 GitHub Actions 全新运行环境的 EVE Online 静态数据构建项目。一次构建生成多语言 SQLite 数据库、图标、地图、长文本、物品详情、版本比较报告和 Release 附件。

## 安装与运行

需要 Python 3.11 或更高版本。在克隆的仓库根目录安装，配置和静态数据随源码工作区使用：

```bash
python -m pip install -e .
python -m evesde --help
python -m evesde build --package
```

安装后也可使用 `evesde` 命令。`pip install -r requirements.txt` 和 `python main.py` 保留为兼容入口；依赖唯一来源为 `pyproject.toml`。

`build` 总是重新构建，不使用上一轮的 `latest.log` 判断是否跳过。`--force-rebuild` 仅为兼容旧命令保留。下载目录用于本次运行中各处理器共享数据，Actions 不保存或恢复这些目录。

## 构建与发布

Actions 使用以下两个命令确定版本并完成构建：

```bash
python -m evesde plan --output tmp/build-plan.json
python -m evesde build --plan tmp/build-plan.json --package
```

`plan` 查询客户端和 SDE 版本，检查已有 Release，并保存构建号、补丁号、发布日期、客户端版本信息及上一版 Release。后续阶段使用这份计划，不再次查询“最新版本”，避免构建过程中上游更新导致编号或比较基线漂移。

上一版基线优先使用 GitHub 的 `latest`；当接口返回 404、空结果或该版本不满足基线要求时，再分页查询 Release 列表。仅考虑 `sde-build-构建号[.两位补丁号]` 的正式版本，分页回退时按构建号和补丁号的数值选择最新且 `sde.zip`、`icons.zip`、`metadata.json` 均已上传的版本。删除最新 Release 后会自动选择剩余的最新完整版本；草稿、预发布、其他项目的 Release 和附件不完整的版本不参与选择。没有正式 SDE Release 时视为首次发布；已有正式版本但全部附件不完整，或 API 查询失败时直接报错，避免误当首次发布。基线确定后若附件被删除，下载失败会终止本次构建。

- 正常模式：相同构建号已发布时跳过。
- `plan --patch`：选择首个未使用的 `.01`～`.99` 补丁号。
- `plan --debug`：始终构建基础版本。Actions 保存检查产物，但不提交历史、不推送、不发布。
- `plan --skip-version-check`：允许客户端与 SDE 构建号不一致，仍记录并使用各自的确定版本。

手动触发工作流的三个选项分别映射为 `BUILD_PATCH`、`DEBUG_MODE` 和 `SKIP_VERSION_CHECK`。GitHub API 使用 `GH_TOKEN`，其次使用 `GITHUB_TOKEN`；目标仓库优先取 `GITHUB_REPOSITORY`，否则取 `config.json` 的 `github_repo`。

构建包含原有的 36 个数据处理步骤，顺序不变。SDE 只下载一次；上一版图标在两份比较报告之间共享。补丁构建比较同一个 CCP 版本时直接使用当前 JSONL，不重复下载。物品详情批量导出复用数据库连接；任何物品导出失败都会阻止发布打包。

数据库差异报告需要 `sqldiff`。Ubuntu 24.04 的安装方式：

```bash
sudo apt-get update
sudo apt-get install -y sqlite3-tools
```

工作流已包含此步骤。其他环境优先从 PATH 查找 `sqldiff`，也兼容仓库中的 `tools/sqldiff`。工具不可用时，版本比较报告会注明；SQLite 数据构建本身不依赖它。

## 跳过只有版本号变化的发布

数据库和图标完成后、物品详情导出和报告打包之前，构建会与**上一版已发布 Release** 比较实际内容：

- SQLite：比较表、索引和视图结构，以及各表全部记录；保留重复行数量和值类型。只忽略 `version_info` 中的 `id`、`build_number`、`patch_number`、`release_date`、`build_key` 数据，不忽略该表的结构和其他字段。
- 图标和长文本 ZIP：比较解压后的文件名与内容，忽略 ZIP 时间戳、压缩方式和文件排列顺序。
- 地图、本地化及其他 SDE 文件：比较内容并检测文件新增、删除；JSON 忽略对象键顺序和缩进，数组顺序仍参与比较。
- 忽略运行记录 `latest.log`、派生报告 `whats_new.json`、SQLite 内部统计和物理页布局，不以数据库文件哈希或报告文本决定是否发布。

只有全部内容一致时才认定为无效更新。该次运行正常结束，但不导出物品详情、不生成发布包、不提交历史、不创建 Release。Actions 仅保留 `publish-decision.json` 和构建计划，并在运行摘要中说明“仅版本信息变化，跳过发布”。首次发布照常进行；补丁构建也采用相同的内容检查。附件下载、数据库或 ZIP 比较失败时构建报错，不会误判为没有变化。

跳过的版本不写入仓库，也不依赖跨次执行缓存。下一次全新运行仍与实际已发布版本比较，确保不会漏掉累积变化。

## 输出与检查

```text
output/
  sde/
    db/item_db.sqlite      # 单库全语言宽列
    texts.zip              # texts.json: {hex_id: text}
    maps/
    localization/
    latest.log
  icons/icons.zip
  item_detail/en/           # 每个物品一个 JSON
  item_detail/zh/
  whats_new/                # 带版本号的 .md 与暂存的 whats_new.json
  release/
    sde.zip
    metadata.json          # 构建/补丁号、图标版本、SHA256
    sde-build-*-all.tar.gz
    release_compare_*.md
    release_notes_*.md
    release-manifest.json  # 附件和历史同步清单
    publish-decision.json  # 实际内容变更及是否继续发布的依据
```

打包检查 SQLite 完整性与非空 types 表、ZIP CRC 和最小体积、长文本包及中英文物品详情。附件名、数据库结构、文本键规则和 metadata 字段保持不变。超过 90 MB 的比较报告不会提交到 Git，也不会在 Release 说明中生成无效的仓库链接。

已有构建可单独重新生成报告或打包：

```bash
python -m evesde reports --plan tmp/build-plan.json
python -m evesde package --plan tmp/build-plan.json
```

历史同步使用另一个干净 checkout：

```bash
python -m evesde sync-history \
  --manifest output/release/release-manifest.json \
  --checkout /path/to/separate-checkout --branch main --push
```

该命令校验源文件，复制报告和物品详情，提交变更，并在指定 `--push` 时推送。调试构建清单不能用于历史同步。Actions 先同步历史再创建 Release，使报告链接可用；任一必需步骤失败都会阻止后续发布。

发布步骤通过 `with.token` 显式传入 `GH_TOKEN`（未配置时使用内置 `GITHUB_TOKEN`），标签指向历史同步后已推送的提交。工作流已声明 `contents: write`；自定义 `GH_TOKEN` 的权限需单独配置，不会被这项声明提升。若使用细粒度 PAT，需授权目标仓库并具备 `Contents: Read and write`；若标签目标提交涉及相对默认分支的工作流修改，还需 `Workflows: Read and write`。修改工作流后应从新提交发起运行，重跑旧任务仍会使用旧工作流。

## 机器可读物品变更

存在实际更新和上一版比较基线时，同时生成 Markdown 和固定名称的 `whats_new.json`。Markdown 加入 Release、全量包及历史提交；JSON 仅打包到 `sde.zip` 根目录。JSON 只有两个字段：`new` 是全部新增 typeID 的整数数组，`modify` 按 typeID 记录已有物品的实际变化，通过 `kind` 区分物品和蓝图。物品记录属性变化，蓝图仅记录各活动的材料变化；值沿用 `old/new` 文本和 `null`。新增物品不重复进入 `modify`，未变化内容不输出，不再包含版本号、图标、名称或描述。

字段定义和完整例子见 [whats_new JSON 格式](docs/whats-new-json.md)。这项输出遵循现有发布内容检测：无实际变化时仍跳过报告生成及发布。

## 项目结构

```text
evesde/
  __main__.py / cli.py      # 统一命令和参数
  application.py           # 应用编排与资源生命周期
  paths.py / build_prep.py  # 配置、路径、版本信息与输出准备
  pipeline.py              # 固定的数据处理顺序
  processors/              # 数据转换及处理器兼容入口
  release/
    plan.py                # 版本选择与构建计划
    baseline.py            # 同次运行的上一版附件共享
    changes.py             # 实际内容比较，跳过只有版本变化的构建
    comparison.py          # 数据库、图标、地图比较
    reports.py             # 物品变更报告
    report_json.py         # ID 为键、old/new 文本的 JSON 格式
    assets.py              # 制品校验、打包、元数据和清单
    history.py             # 历史同步与 Git 提交
  github.py                # GitHub API、附件与 Actions 输出
  maintenance.py           # 过期 Actions 产物清理
  icon_builder/            # 图标生成库
  localization/ / brackets/
  utils/                   # HTTP、下载、数据库和多语言工具
data/                      # 静态输入
tools/                     # 开发辅助工具，不参与正式流水线
tests/                     # 离线单元与集成测试
```

## GitHub Actions

- `auto-sde-build.yml`：一个作业完成版本计划、构建打包、检查产物上传、历史同步和发布。工作流只承担运行环境、条件、权限和发布动作；不在 YAML 内实现版本选择、文件复制或 Git 提交逻辑。
- `checks.yml`：PR 和相关源码变更检查项目安装、Python 编译和命令行入口，不运行离线回归测试。
- `remove-old-artifacts.yml`：保留手动入口，调用 `clean-artifacts --days 5 --keep 5`，保留最近 5 个产物并删除其余超过 5 天的产物。

构建和发布在同一个工作目录完成，不再生成或跨作业传递 `dist-ci.tar.gz`。检查产物保留 5 天；ZIP/tar 包上传时不再重复压缩。运行摘要覆盖整个作业结果，发布失败不会显示成构建发布成功。

## 开发验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q evesde main.py
python -m evesde --help
```

测试不访问网络、不修改已有 output、不推送仓库或创建 Release。覆盖版本选择、补丁耗尽、调试模式、HTTP 失败、下载中断、CRC、批量物品导出、真实 SQLite/ZIP/tar 打包、哈希、临时 Git 历史提交及产物清理。线上全量构建通过 Actions 手动触发的 `debug` 模式验证。

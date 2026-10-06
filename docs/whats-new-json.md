# whats_new JSON 格式（schema_version = 1）

当构建发现实际发布内容变化，且存在可比较的上一版 SDE Release 时，在同一轮分析中生成：

```text
output/whats_new/whats_new_<旧CCP版本>_<新发布版本>.md
output/whats_new/whats_new_<旧CCP版本>_<新发布版本>.json
```

两个文件同时作为 Release 附件、全量 tar 包成员和仓库历史文件保存。缺少其中任何一个都不能打包发布。只有版本号变化的运行仍在报告生成前退出，不会为了生成 JSON 而创建无效发布。首次发布没有比较基线，因此不生成这对报告。

## 通用约定

- 编码为 UTF-8，顶层是对象，`schema_version` 是数字 `1`。
- 实体使用 ID 字符串作为对象键。物品、属性、组别、类别、蓝图和材料均不包含显示名称，无论中文或英文。
- 变更叶子是 `{"old": "旧值文本", "new": "新值文本"}`。数值也使用字符串；整数值浮点数规范化为整数文本，如 `10.0` 输出 `"10"`。
- 一侧不存在时使用 JSON `null`；数值零是字符串 `"0"`，空文本是 `""`，两者都不是 `null`。
- 不使用 `"10 -> 20"`、中文“新增”等需要再次解析的展示字符串。
- 空变更分类使用 `{}`。对象键稳定排序，不应依赖键顺序；数组内容（若作为字段值出现）使用紧凑 JSON 文本。
- 描述正文属于数据，保留现有 Markdown 报告使用的文本（优先中文、回退英文，去 HTML 和多余空白）。它不是物品名称。

## 顶层字段

| 字段 | 内容 |
| --- | --- |
| `schema_version` | 格式版本，当前为 `1` |
| `versions` | `old`、`new` 为实际发布版本字符串，保留补丁号；不从文件名推断 |
| `new_items` | `typeID` → 新物品的 `group_id`、`category_id`、描述和属性 |
| `new_ships` | 新飞船 `typeID` → `blueprint_id` 及材料数量；找不到蓝图时 ID 为 `null`、材料为 `{}` |
| `blueprint_changes` | 蓝图 ID → `status` 和嵌套字段差异 `changes` |
| `attribute_changes` | `typeID` → `attributeID` → `old` / `new` |
| `icon_changes` | 图标文件名 → 新旧内容 SHA256 文本；新增/删除的一侧为 `null` |

`new_items` 的 `group_id`、`category_id` 和 `new_ships` 的 `blueprint_id` 是 ID 字符串或 `null`。`new_items.attributes` 和 `new_ships.materials` 的值同样使用 `old` / `new`，新增项的 `old` 为 `null`。新物品的零值属性保留在 JSON 中，即使 Markdown 为简洁而未展示。

物品属性的类别范围沿用现有分析器：`4、6、7、18、20、65、66、87`。这是物品变更报告，范围不等同于整个 SDE 的所有数据差异；例如仅地图更新时，物品相关分类可能为空。

## 属性变化示例

以下 ID 和数值仅演示格式：

```json
{
  "schema_version": 1,
  "versions": {"old": "3561556", "new": "3569502"},
  "new_items": {},
  "new_ships": {},
  "blueprint_changes": {},
  "attribute_changes": {
    "587": {
      "20": {"old": "10", "new": "12.5"},
      "21": {"old": null, "new": "0"},
      "22": {"old": "5", "new": null}
    }
  },
  "icon_changes": {}
}
```

上述分别表示属性修改、增加值为零的属性、删除属性。消费者只需用物品与属性 ID 查询自己的名称资源。

## 蓝图变化

`status` 固定为 `added`、`removed` 或 `changed`。`changes` 保留 SDE 字段层级；材料、产品和技能列表转为 `typeID` 映射，避免列表重排形成假变更。制造、反应、研究等全部活动及其字段都会记录，不局限于 Markdown 详细展示的制造/反应数量。

```json
{
  "100": {
    "status": "changed",
    "changes": {
      "maxProductionLimit": {"old": "10", "new": "20"},
      "activities": {
        "manufacturing": {
          "time": {"old": "100", "new": "120"},
          "materials": {
            "34": {"quantity": {"old": "1000", "new": "800"}}
          },
          "products": {
            "587": {"probability": {"old": "0.5", "new": "0.8"}}
          }
        },
        "research_time": {
          "skills": {
            "3402": {"level": {"old": null, "new": "3"}}
          }
        }
      }
    }
  }
}
```

新增和删除蓝图也使用相同的字段差异结构，对应一侧为 `null`。JSON 保留完整图标变更列表，不受 Markdown 每类最多显示 200 个图标的限制。

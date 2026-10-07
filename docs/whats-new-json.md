# whats_new.json：物品级差异格式

JSON 位于 `sde.zip` 根目录，固定命名为 `whats_new.json`。只含 `new` 和 `modify` 两个顶层字段，值分别为新增 typeID 数组和已有物品的差异字典。

存在实际更新且有上一版比较基线时生成；首次发布可能没有此文件。没有相关物品变化时为 `{"new": [], "modify": {}}`。报告是派生数据，不参与是否发布的内容比较。Markdown 报告仍使用带版本号的文件名和原有分类，保留 Release 附件与仓库历史；JSON 仅随 sde.zip 交付。

## new：新增物品

整数数组，记录新版本 `types` 中新增的全部 typeID，按数值排序，包括新增蓝图。不按类别或 published 状态过滤，不记录初始属性或蓝图详情，也不会重复出现在 modify 中。名称与完整数据由消费者查询当前数据库。

## modify：已有物品的变化

以 typeID 字符串为键，只比较新旧版本 `types` 均存在的物品。有实际差异才输出条目；整个物品删除不在本格式中记录。

每个条目包含：

- `kind`：`item` 或 `blueprint`。新旧任一版本含对应 blueprints 记录即视为蓝图。
- `attributes`：可选，attributeID → old/new。记录 typeDogma 属性的新增、删除和修改，无类别限制；已有物品首次获得属性也会记录。
- `blueprint`：可选，蓝图字段的嵌套差异。仅记录各活动中 materials 的材料新增、删除和数量变化，忽略技能、时间、产品、概率及 maxProductionLimit 等字段。只输出变化的字段。

蓝图不记录 dogma 属性变化；只有材料发生变化才输出。已有物品获得或失去蓝图材料数据时，记录对应材料的新增或删除。typeID 已是键，不重复输出 _key、blueprintTypeID 或显示名称。

## 值与嵌套结构

变化叶子固定为 `{"old": "旧值", "new": "新值"}`，数值也用字符串；整数值浮点数规范化为整数文本。缺失一侧为 null，不能与字符串 "0" 或空字符串混淆。

蓝图保留 activities → 活动名 → 字段的结构。materials 从列表转为材料 typeID 字符串键的对象，记录 quantity。仅列表重排不视为变化，未变化的材料或字段不输出。

### 同一活动中重复的 typeID

源 SDE 的材料列表可能多次出现相同 typeID。唯一 ID 仍使用上面的字段级差异结构；重复 ID 则保留全部记录及重复次数，按内容稳定排序，不求和、不取最大值、不覆盖。

当重复记录变化，或某 ID 在单条和多条之间变化时，该 ID 直接输出 old/new，值为对象或数组的紧凑 JSON 文本，例如：

```json
{"34": {"old": "[{\"quantity\":1},{\"quantity\":2}]", "new": "[{\"quantity\":1},{\"quantity\":3}]"}}
```

消费者对这一叶子的文本再次解析即可取得完整记录；缺失的一侧仍为 null。仅重复列表的排列顺序变化不会产生差异。

## 示例

以下数据仅演示格式：

```json
{
  "new": [95533, 95534],
  "modify": {
    "587": {
      "kind": "item",
      "attributes": {
        "20": {"old": "10", "new": "12.5"},
        "21": {"old": null, "new": "0"},
        "22": {"old": "5", "new": null}
      }
    },
    "100": {
      "kind": "blueprint",
      "blueprint": {
        "activities": {
          "manufacturing": {
            "materials": {
              "34": {"quantity": {"old": "1000", "new": "800"}}
            }
          }
        }
      }
    }
  }
}
```

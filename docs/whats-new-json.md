# whats_new.json：物品级差异格式

JSON 位于 `sde.zip` 根目录，固定命名为 `whats_new.json`。只含 `new` 和 `modify` 两个顶层字段，不含版本号、名称、描述、图标分类或 schema_version。此格式替代之前的分类式 JSON，消费者需同步调整，不能按旧格式读取。

存在实际更新且有上一版比较基线时生成；首次发布可能没有此文件。没有相关物品变化时为 `{"new": [], "modify": {}}`。报告是派生数据，不参与是否发布的内容比较。Markdown 报告仍使用带版本号的文件名和原有分类，保留 Release 附件与仓库历史；JSON 仅随 sde.zip 交付。

## new：新增物品

整数数组，记录新版本 `types` 中新增的全部 typeID，按数值排序，包括新增蓝图。不按类别或 published 状态过滤，不记录初始属性或蓝图详情，也不会重复出现在 modify 中。名称与完整数据由消费者查询当前数据库。

## modify：已有物品的变化

以 typeID 字符串为键，只比较新旧版本 `types` 均存在的物品。有实际差异才输出条目；整个物品删除不在本格式中记录。

每个条目包含：

- `kind`：`item` 或 `blueprint`。新旧任一版本含对应 blueprints 记录即视为蓝图。
- `attributes`：可选，attributeID → old/new。记录 typeDogma 属性的新增、删除和修改，无类别限制；已有物品首次获得属性也会记录。
- `blueprint`：可选，蓝图字段的嵌套差异。记录全部活动中的材料、技能、时间、产品、概率，以及 maxProductionLimit 等字段。只输出变化的字段。

蓝图也可能有 dogma 属性变化，此时同一个条目同时包含 attributes 和 blueprint；两者均无变化时不输出。已有物品获得或失去蓝图数据时，记录对应字段的新增或删除。typeID 已是键，不重复输出 _key、blueprintTypeID 或显示名称。

## 值与嵌套结构

变化叶子固定为 `{"old": "旧值", "new": "新值"}`，数值也用字符串；整数值浮点数规范化为整数文本。缺失一侧为 null，不能与字符串 "0" 或空字符串混淆。

蓝图保留 activities → 活动名 → 字段的结构。materials、products、skills 从列表转为 typeID 字符串键的对象，内部保留 quantity、level、probability 等字段。仅列表重排不视为变化，未变化的材料、技能或字段不输出。其他数组若变化，作为紧凑 JSON 文本放入 old/new。

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
        "maxProductionLimit": {"old": "10", "new": "20"},
        "activities": {
          "manufacturing": {
            "time": {"old": "100", "new": "120"},
            "materials": {
              "34": {"quantity": {"old": "1000", "new": "800"}}
            },
            "skills": {
              "3402": {"level": {"old": "2", "new": "3"}}
            },
            "products": {
              "587": {"probability": {"old": "0.5", "new": "0.8"}}
            }
          }
        }
      }
    }
  }
}
```

旧样例不能可靠地直接转换成完整的新格式：旧版属性比较有类别限制，可能缺少新格式所需的数据。生成准确历史报告需使用两版原始 SDE 重新比较。

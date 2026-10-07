"""机器报告直接来自 SDE 分析结果，验证 ID、文本值和发布边界。"""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from evesde.processors.item_changes_analyzer import main
from evesde.release.report_json import field_changes, normalize_blueprint


class JSONReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.old, self.new = self.root / "old", self.root / "new"
        self.old.mkdir()
        self.new.mkdir()
        self.destination = self.root / "whats_new_122_123.md"
        self.write_both("types", [self.item(1), self.item(100), self.item(300)],
                        [self.item(1), self.item(2), self.item(3, group=999), self.item(100), self.item(200), self.item(300)])
        self.write_both("groups", [{"_key": 10, "categoryID": 6, "name": {"zh": "中文组名"}}])
        self.write_both("categories", [{"_key": 6, "name": {"zh": "中文类别名"}}])
        self.write_both("dogmaAttributes", [{"_key": i, "displayName": {"zh": "中文属性名"}} for i in range(10, 16)])
        self.write_both("typeDogma", [self.dogma(1, {10: 10.0, 11: 0, 12: 4})],
                        [self.dogma(1, {10: 12.5, 13: 0}), self.dogma(2, {14: 0, 15: 5})])
        blueprint_old = {"_key": 100, "blueprintTypeID": 100, "maxProductionLimit": 10, "activities": {
            "manufacturing": {"time": 10, "materials": [{"typeID": 34, "quantity": 100}],
                              "products": [{"typeID": 1, "quantity": 1, "probability": 0.5}]}}}
        blueprint_new = {"_key": 100, "blueprintTypeID": 100, "maxProductionLimit": 20, "activities": {
            "manufacturing": {"time": 12, "materials": [{"typeID": 35, "quantity": 200}],
                              "products": [{"typeID": 1, "quantity": 1, "probability": 0.8}]},
            "research_time": {"time": 50, "skills": [{"typeID": 3402, "level": 3}]}}}
        blueprint_added = {"_key": 200, "activities": {"manufacturing": {
            "materials": [{"typeID": 34, "quantity": 2}], "products": [{"typeID": 2, "quantity": 1}]}}}
        blueprint_removed = {"_key": 300, "activities": {"reaction": {"time": 10}}}
        self.write_both("blueprints", [blueprint_old, blueprint_removed], [blueprint_new, blueprint_added])
        self.old_icons, self.new_icons = self.root / "old.zip", self.root / "new.zip"
        for filename, files in ((self.old_icons, {"1.png": b"old", "3.png": b"removed"}),
                                (self.new_icons, {"1.png": b"new", "2.png": b"added"})):
            with zipfile.ZipFile(filename, "w") as archive:
                for name, content in files.items():
                    archive.writestr(name, content)

    @staticmethod
    def item(type_id, group=10):
        return {"_key": type_id, "groupID": group, "name": {"zh": "中文物品名"},
                "description": {"zh": "<b>保留描述文本</b>"}}

    @staticmethod
    def dogma(type_id, values):
        return {"_key": type_id, "dogmaAttributes": [{"attributeID": key, "value": value} for key, value in values.items()]}

    def write_both(self, name, old, new=None):
        for directory, records in ((self.old, old), (self.new, new if new is not None else old)):
            (directory / f"{name}.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records), encoding="utf-8")

    def generate(self):
        self.assertTrue(main({}, self.old, self.new, self.destination,
                             old_icons_zip=self.old_icons, current_icons_zip=self.new_icons,
                             old_version="122.01", new_version="123.02"))
        return json.loads(self.destination.with_name("whats_new.json").read_text(encoding="utf-8"))

    def test_names_omitted_and_before_after_values_are_text(self):
        report = self.generate()
        raw = self.destination.with_name("whats_new.json").read_text()
        for name in ("中文物品名", "中文属性名", "中文组名", "中文类别名"):
            self.assertNotIn(name, raw)
        self.assertIn("中文物品名", self.destination.read_text())
        self.assertEqual(set(report), {"new", "modify"})
        self.assertEqual(report["new"], [2, 3, 200])
        self.assertEqual(report["modify"]["1"]["kind"], "item")
        self.assertEqual(report["modify"]["1"]["attributes"], {
            "10": {"old": "10", "new": "12.5"}, "11": {"old": "0", "new": None},
            "12": {"old": "4", "new": None}, "13": {"old": None, "new": "0"},
        })
        self.assertNotIn("2", report["modify"])
        self.assertNotIn("200", report["modify"])
        self.assertNotIn("  - 属性:", self.destination.read_text())

    def test_all_blueprint_changes_keep_ids_without_names(self):
        report = self.generate()
        self.assertEqual(report["modify"]["100"]["kind"], "blueprint")
        changes = report["modify"]["100"]["blueprint"]
        self.assertEqual(changes["maxProductionLimit"], {"old": "10", "new": "20"})
        manufacturing = changes["activities"]["manufacturing"]
        self.assertEqual(manufacturing["materials"]["34"]["quantity"], {"old": "100", "new": None})
        self.assertEqual(manufacturing["materials"]["35"]["quantity"], {"old": None, "new": "200"})
        self.assertEqual(manufacturing["products"]["1"]["probability"], {"old": "0.5", "new": "0.8"})
        self.assertEqual(changes["activities"]["research_time"]["skills"]["3402"]["level"], {"old": None, "new": "3"})
        self.assertNotIn("blueprintTypeID", changes)
        self.assertEqual(report["modify"]["300"]["blueprint"]["activities"]["reaction"]["time"],
                         {"old": "10", "new": None})

    def test_attributes_are_not_restricted_to_markdown_categories(self):
        self.write_both("types", [self.item(1, group=999)])
        self.assertIn("1", self.generate()["modify"])

    def test_existing_item_can_gain_its_first_attribute(self):
        self.write_both("typeDogma", [], [self.dogma(1, {10: 0})])
        self.assertEqual(self.generate()["modify"]["1"]["attributes"],
                         {"10": {"old": None, "new": "0"}})

    def test_blueprint_can_also_have_attribute_changes(self):
        self.write_both("typeDogma", [self.dogma(100, {10: 1})], [self.dogma(100, {10: 2})])
        item = self.generate()["modify"]["100"]
        self.assertEqual(item["kind"], "blueprint")
        self.assertIn("attributes", item)
        self.assertIn("blueprint", item)

    def test_icons_do_not_change_machine_report(self):
        first = self.generate()
        with zipfile.ZipFile(self.new_icons, "a") as archive:
            archive.writestr("999.png", b"changed")
        self.assertEqual(first, self.generate())

    def test_json_output_is_deterministic(self):
        self.generate()
        first = self.destination.with_name("whats_new.json").read_bytes()
        self.generate()
        self.assertEqual(first, self.destination.with_name("whats_new.json").read_bytes())

    def test_blueprint_list_reordering_is_not_a_change(self):
        old = {"materials": [{"typeID": 34, "quantity": 1}, {"typeID": 35, "quantity": 2}]}
        new = {"materials": list(reversed(old["materials"]))}
        self.assertIsNone(field_changes(normalize_blueprint(old), normalize_blueprint(new)))

    def test_field_structure_change_preserves_both_values(self):
        self.assertEqual(field_changes({"value": 1}, "replacement"),
                         {"old": '{"value":1}', "new": "replacement"})

    def test_duplicate_material_ids_fail_instead_of_overwriting(self):
        with self.assertRaisesRegex(ValueError, "重复"):
            normalize_blueprint({"materials": [{"typeID": 34, "quantity": 1}, {"typeID": 34, "quantity": 2}]})

    def test_unchanged_report_sections_are_empty_objects(self):
        self.assertTrue(main({}, self.old, self.old, self.destination, old_version="122", new_version="122"))
        report = json.loads(self.destination.with_name("whats_new.json").read_text())
        self.assertEqual(report, {"new": [], "modify": {}})



if __name__ == "__main__":
    unittest.main()

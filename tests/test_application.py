"""验证应用边界、失败传播和批量导出，而不运行线上数据处理器。"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from evesde import application
from evesde.paths import ensure_dirs
from evesde.processors.item_detail_extractor import ItemDetailExtractor
from test_release import plan


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = {"paths": {name: str(root / name) for name in
                                ("client_cache", "db_output", "item_detail_en", "item_detail_zh", "release_output")}}
        self.patches = {}
        for name in ("build_prep", "EveClient", "set_eve_client", "sde_downloader", "AccountingTypesLocalizer",
                     "parse_brackets", "run_pipeline", "version_info_processor", "compression_processor",
                     "item_detail_extractor", "generate_reports", "assets", "detect_changes", "output"):
            mock = patch.object(application, name)
            self.patches[name] = mock.start()
            self.addCleanup(mock.stop)
        self.patches["detect_changes"].return_value.has_changes = True
        self.patches["detect_changes"].return_value.reasons = ["test change"]
        for name in ("sde_downloader", "version_info_processor", "compression_processor"):
            self.patches[name].main.return_value = True
        self.patches["item_detail_extractor"].item_detail_extract.return_value = True

    def test_build_uses_plan_without_requery_and_releases_client(self):
        selected = plan()
        application.run_build(self.config, selected, package=True)
        self.patches["EveClient"].from_tq.assert_called_once_with(
            Path(self.config["paths"]["client_cache"]), client_data=selected.client_data)
        self.patches["sde_downloader"].main.assert_called_once()
        self.assertEqual(self.patches["sde_downloader"].main.call_args.kwargs["build_number"], "123")
        self.patches["generate_reports"].assert_called_once()
        self.patches["assets"].prepare_release.assert_called_once()
        self.patches["EveClient"].from_tq.return_value.close.assert_called_once()
        self.patches["set_eve_client"].assert_called_with(None)
        self.assertNotIn("eve_client", self.config)
        self.assertNotIn("sde_build_number", self.config)

    def test_debug_build_never_requests_publish(self):
        application.run_build(self.config, plan(debug=True), package=True)
        self.patches["assets"].prepare_release.assert_called_once()
        self.assertNotIn(unittest.mock.call("should-publish", True), self.patches["output"].mock_calls)

    def test_partial_details_block_log_and_packaging(self):
        self.patches["item_detail_extractor"].item_detail_extract.side_effect = [True, False]
        with self.assertRaisesRegex(RuntimeError, "zh"):
            application.run_build(self.config, plan(), package=True)
        self.patches["assets"].prepare_release.assert_not_called()
        self.patches["build_prep"].write_latest_log.assert_not_called()
        self.patches["EveClient"].from_tq.return_value.close.assert_called_once()

    def test_skipped_plan_has_no_build_side_effects(self):
        application.run_build(self.config, plan(should_build=False), package=True)
        for name, mock in self.patches.items():
            if name not in ("output", "detect_changes"):
                self.assertEqual(mock.mock_calls, [])

    def test_version_only_skips_export_reports_and_packaging(self):
        self.patches["detect_changes"].return_value.has_changes = False
        application.run_build(self.config, plan(), package=True)
        self.patches["item_detail_extractor"].item_detail_extract.assert_not_called()
        self.patches["generate_reports"].assert_not_called()
        self.patches["assets"].prepare_release.assert_not_called()
        self.patches["EveClient"].from_tq.return_value.close.assert_called_once()
        self.patches["output"].assert_any_call("has-changes", False)
        self.assertNotIn(unittest.mock.call("should-publish", True), self.patches["output"].mock_calls)

    def test_comparison_error_prevents_release(self):
        self.patches["detect_changes"].side_effect = RuntimeError("bad baseline")
        with self.assertRaisesRegex(RuntimeError, "bad baseline"):
            application.run_build(self.config, plan(), package=True)
        self.patches["assets"].prepare_release.assert_not_called()
        self.patches["EveClient"].from_tq.return_value.close.assert_called_once()

    def test_dotted_directory_is_created_as_directory(self):
        destination = Path(self.temp.name) / "data.v1"
        ensure_dirs({"paths": {"sde_input": str(destination)}})
        self.assertTrue(destination.is_dir())


class ItemDetailTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        db_dir = self.root / "db"
        db_dir.mkdir()
        self.db = db_dir / "item_db.sqlite"
        with closing(sqlite3.connect(self.db)) as conn:
            conn.executescript('''
                CREATE TABLE types (type_id INTEGER PRIMARY KEY, published, categoryID,
                    en_name, zh_name, en_desc_id, zh_desc_id, group_en_name, group_zh_name,
                    category_en_name, category_zh_name, volume, repackaged_volume, capacity, mass);
                INSERT INTO types VALUES (1,1,6,'Ship','飞船','0','a','Group','组','Ships','舰船',10,5,2,100);
                INSERT INTO types SELECT 2,1,6,'Second','第二艘','0','a','Group','组','Ships','舰船',20,5,2,100;
                INSERT INTO types SELECT 3,1,91,'Excluded','不导出','0','a','Group','组','Ships','舰船',20,5,2,100;
                CREATE TABLE typeAttributes (type_id,attribute_id,value);
                INSERT INTO typeAttributes VALUES (1,10,42);
                CREATE TABLE dogmaAttributes (attribute_id,attribute_key,categoryID,en_name,zh_name,unit_en_name,unit_zh_name);
                INSERT INTO dogmaAttributes VALUES (10,'speed',1,'Speed','速度','m/s','米/秒');
                CREATE TABLE traits (typeid,bonus_type,importance,en_content,zh_content);
                INSERT INTO traits VALUES (1,'roleBonuses',1,'Role','角色');
            ''')
        with zipfile.ZipFile(self.root / "texts.zip", "w") as archive:
            archive.writestr("texts.json", json.dumps({"0": "description", "a": "描述"}))

    def test_batch_preserves_single_query_output_with_one_connection(self):
        for lang, name, description in (("en", "Ship", "description"), ("zh", "飞船", "描述")):
            extractor = ItemDetailExtractor(str(self.db), str(self.root / lang), lang)
            expected = extractor.get_item_detail(1)
            real_connect = sqlite3.connect
            with patch("evesde.processors.item_detail_extractor.sqlite3.connect", wraps=real_connect) as connect:
                self.assertTrue(extractor.extract_all_items())
            connect.assert_called_once()
            result = json.loads((self.root / lang / "item_1.json").read_text())
            self.assertEqual(result, expected)
            self.assertEqual((result["name"], result["description"]), (name, description))
            self.assertEqual(result["attributes"][0]["value"], 42)
            self.assertFalse((self.root / lang / "item_3.json").exists())
            self.assertIsNone(extractor._shared_connection)

    def test_any_failed_item_fails_batch_and_closes_connection(self):
        extractor = ItemDetailExtractor(str(self.db), str(self.root / "out"))
        with patch.object(extractor, "save_item_detail", side_effect=[True, False]):
            self.assertFalse(extractor.extract_all_items())
        self.assertIsNone(extractor._shared_connection)


if __name__ == "__main__":
    unittest.main()

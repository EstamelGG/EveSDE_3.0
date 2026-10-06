"""发布跳过必须基于实际内容；覆盖版本字段、存储布局和真实数据变更。"""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

from evesde.release.changes import database_changes, detect_changes, files_equal
from test_release import plan


class ContentChangesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.old, self.new = self.root / "old", self.root / "new"
        for folder in (self.old, self.new):
            (folder / "db").mkdir(parents=True)
        self.old_db = self.old / "db/item_db.sqlite"
        self.new_db = self.new / "db/item_db.sqlite"
        with closing(sqlite3.connect(self.old_db)) as db:
            db.executescript('''
                CREATE TABLE types (type_id INTEGER PRIMARY KEY, name TEXT, value BLOB);
                INSERT INTO types VALUES (1,'ship',X'0102');
                CREATE TABLE duplicates (value);
                INSERT INTO duplicates VALUES ('a'), ('a'), ('b');
                CREATE TABLE version_info (id INTEGER PRIMARY KEY AUTOINCREMENT, build_number INTEGER,
                    patch_number INTEGER, release_date TEXT, build_key TEXT, description TEXT);
                INSERT INTO version_info VALUES (1,122,0,'yesterday','sde','version');
            ''')
        shutil.copy2(self.old_db, self.new_db)
        self.execute("UPDATE version_info SET id=9, build_number=123, patch_number=1, release_date='today', build_key='new'")
        self.config = {"paths": {"sde_output": str(self.new), "icons_output": str(self.root / "icons"),
                                 "release_output": str(self.root / "release")}}
        (self.root / "icons").mkdir()
        self.old_icons = self.root / "old-icons.zip"
        self.new_icons = self.root / "icons/icons.zip"
        self.write_zip(self.old_icons, {"1.png": b"image"}, (2024, 1, 1, 0, 0, 0))
        self.write_zip(self.new_icons, {"1.png": b"image"}, (2026, 1, 1, 0, 0, 0))
        for directory in (self.old, self.new):
            self.write_zip(directory / "texts.zip", {"texts.json": b'{"0":"text"}'})
            (directory / "map.json").write_text('{"a":1,"b":2}')
        (self.old / "latest.log").write_text('{"build_number":122}')
        self.baseline = Mock(release={"tag_name": "sde-build-122"})
        self.baseline.sde_directory.return_value = self.old
        self.baseline.asset.return_value = self.old_icons

    def execute(self, query):
        with closing(sqlite3.connect(self.new_db)) as db:
            db.executescript(query)

    @staticmethod
    def write_zip(filename, files, timestamp=(2024, 1, 1, 0, 0, 0)):
        with zipfile.ZipFile(filename, "w") as archive:
            for name, content in files.items():
                info = zipfile.ZipInfo(name, date_time=timestamp)
                archive.writestr(info, content)

    def decision(self):
        return detect_changes(self.config, plan(), self.baseline)

    def test_version_only_and_zip_timestamps_do_not_publish(self):
        result = self.decision()
        self.assertFalse(result.has_changes)
        self.assertEqual(result.previous_tag, "sde-build-122")
        self.assertNotEqual(self.old_icons.read_bytes(), self.new_icons.read_bytes())
        result.save(self.config)
        saved = json.loads((self.root / "release/publish-decision.json").read_text())
        self.assertFalse(saved["has_changes"])

    def test_row_order_and_sqlite_statistics_do_not_publish(self):
        self.execute("DELETE FROM duplicates; INSERT INTO duplicates VALUES ('b'),('a'),('a'); ANALYZE; VACUUM;")
        self.assertFalse(self.decision().has_changes)

    def test_business_row_change_publishes(self):
        self.execute("UPDATE types SET name='new ship' WHERE type_id=1")
        result = self.decision()
        self.assertTrue(result.has_changes)
        self.assertIn("数据库表内容变化: types", result.reasons)

    def test_duplicate_multiplicity_change_publishes(self):
        # 行数与 DISTINCT 集合都不变，但数据的多重集合改变。
        self.execute("DELETE FROM duplicates; INSERT INTO duplicates VALUES ('a'),('b'),('b');")
        self.assertTrue(self.decision().has_changes)

    def test_sqlite_value_type_change_publishes(self):
        self.execute("UPDATE duplicates SET value=1 WHERE value='a'")
        with closing(sqlite3.connect(self.old_db)) as db:
            db.execute("UPDATE duplicates SET value=1.0 WHERE value='a'")
            db.commit()
        self.assertTrue(self.decision().has_changes)

    def test_schema_change_publishes_even_with_no_new_rows(self):
        self.execute("CREATE TABLE new_table (id INTEGER PRIMARY KEY)")
        self.assertIn("数据库结构变化", self.decision().reasons)

    def test_version_table_schema_change_is_not_ignored(self):
        self.execute("ALTER TABLE version_info ADD COLUMN extra TEXT")
        self.assertTrue(self.decision().has_changes)

    def test_version_description_is_not_ignored(self):
        self.execute("UPDATE version_info SET description='different'")
        self.assertTrue(self.decision().has_changes)

    def test_database_application_id_change_publishes(self):
        self.execute("PRAGMA application_id=1234")
        self.assertTrue(self.decision().has_changes)

    def test_text_only_change_publishes(self):
        self.write_zip(self.new / "texts.zip", {"texts.json": b'{"0":"changed"}'})
        self.assertIn("SDE 文件内容变化: texts.zip", self.decision().reasons)

    def test_icon_only_change_publishes(self):
        self.write_zip(self.new_icons, {"1.png": b"different"})
        self.assertIn("图标文件变化", self.decision().reasons)

    def test_json_key_order_and_whitespace_do_not_publish(self):
        (self.new / "map.json").write_text('{\n"b":2, "a":1\n}')
        self.assertFalse(self.decision().has_changes)

    def test_map_change_and_added_file_publish(self):
        (self.new / "map.json").write_text('{"a":3,"b":2}')
        (self.new / "new.json").write_text('{}')
        result = self.decision()
        self.assertIn("SDE 文件内容变化: map.json", result.reasons)
        self.assertIn("SDE 文件新增/删除: new.json", result.reasons)

    def test_deleted_file_publishes(self):
        (self.new / "map.json").unlink()
        self.assertTrue(self.decision().has_changes)

    def test_first_release_always_publishes(self):
        self.baseline.release = None
        self.assertTrue(self.decision().has_changes)
        self.baseline.asset.assert_not_called()

    def test_missing_current_database_is_an_error(self):
        self.new_db.unlink()
        with self.assertRaisesRegex(RuntimeError, "必需产物"):
            self.decision()

    def test_corrupt_database_never_means_unchanged(self):
        self.old_db.write_bytes(b"bad database")
        with self.assertRaises(sqlite3.DatabaseError):
            self.decision()

    def test_missing_attachment_never_means_unchanged(self):
        self.baseline.asset.side_effect = RuntimeError("missing icons")
        with self.assertRaisesRegex(RuntimeError, "missing icons"):
            self.decision()

    def test_corrupt_zip_never_means_unchanged(self):
        self.old_icons.write_bytes(b"bad zip")
        with self.assertRaises(zipfile.BadZipFile):
            self.decision()

    def test_empty_blob_and_null_are_distinct(self):
        self.execute("UPDATE types SET value=NULL")
        self.assertTrue(database_changes(self.old_db, self.new_db))

    def test_zip_file_order_is_not_a_change(self):
        self.write_zip(self.old_icons, {"1.png": b"one", "2.png": b"two"})
        self.write_zip(self.new_icons, {"2.png": b"two", "1.png": b"one"})
        self.assertTrue(files_equal(self.old_icons, self.new_icons))


if __name__ == "__main__":
    unittest.main()

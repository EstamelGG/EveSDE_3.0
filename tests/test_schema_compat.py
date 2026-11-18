"""SDE schema 兼容、蓝图导入和外部可选数据的回归测试。"""

from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from evesde.icon_builder.sde import read_skin_materials
from evesde.processors.blueprints_processor import BlueprintsProcessor
from evesde.processors.loyalty_stores_processor import (
    LoyaltyStoreError,
    LoyaltyStoresProcessor,
)
from evesde.sde_schema import SdeSchemaError, validate_jsonl_file, validate_sde_directory


class SchemaValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write(self, name, lines):
        path = self.root / name
        path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
        return path

    def test_current_blueprint_schema_does_not_require_removed_field(self):
        path = self.write("blueprints.jsonl", [{
            "_key": 683,
            "activities": {
                "manufacturing": {
                    "time": 6000,
                    "materials": [{"typeID": 34, "quantity": 100}],
                    "products": [{"typeID": 582, "quantity": 1}],
                    "skills": [{"typeID": 3380, "level": 1}],
                }
            },
            "maxProductionLimit": 30,
        }])
        self.assertEqual(
            validate_jsonl_file(path, ("_key", "activities", "maxProductionLimit")), 1
        )

    def test_missing_required_field_is_schema_error(self):
        path = self.write("blueprints.jsonl", [{"_key": 683, "activities": {}}])
        with self.assertRaisesRegex(SdeSchemaError, "maxProductionLimit"):
            validate_jsonl_file(path, ("_key", "activities", "maxProductionLimit"))

    def test_missing_required_file_is_schema_error(self):
        with self.assertRaisesRegex(SdeSchemaError, "不存在"):
            validate_sde_directory(self.root, {"blueprints.jsonl": ("_key",)})

    def test_empty_required_file_is_schema_error(self):
        (self.root / "blueprints.jsonl").write_text("\n\n", encoding="utf-8")
        with self.assertRaisesRegex(SdeSchemaError, "为空"):
            validate_sde_directory(self.root, {"blueprints.jsonl": ("_key",)})

    def test_invalid_json_is_schema_error(self):
        path = self.root / "blueprints.jsonl"
        path.write_text('{"_key": 1}\nnot json\n', encoding="utf-8")
        with self.assertRaisesRegex(SdeSchemaError, "不是合法 JSON"):
            validate_jsonl_file(path, ("_key",))

    def test_nested_blueprint_activity_change_is_schema_error(self):
        self.write("blueprints.jsonl", [{
            "_key": 683,
            "activities": {
                "manufacturing": {
                    "time": 6000,
                    "materials": [{"typeID": 34}],
                }
            },
            "maxProductionLimit": 30,
        }])
        with self.assertRaisesRegex(SdeSchemaError, "quantity"):
            validate_sde_directory(self.root, {"blueprints.jsonl": ("_key", "activities")})


class BlueprintCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sde = self.root / "sde"
        self.sde.mkdir()
        self.config = {
            "paths": {"sde_input": str(self.sde), "db_output": str(self.root / "db")},
            "languages": ["en"],
        }

    def test_blueprint_uses_key_as_type_id_and_ignores_removed_field(self):
        record = {
            "_key": 683,
            "blueprintTypeID": 999999,
            "activities": {
                "manufacturing": {
                    "time": 6000,
                    "materials": [{"typeID": 34, "quantity": 100}],
                    "products": [{"typeID": 582, "quantity": 1}],
                    "skills": [{"typeID": 3380, "level": 1}],
                }
            },
            "maxProductionLimit": 30,
        }
        (self.sde / "blueprints.jsonl").write_text(json.dumps(record), encoding="utf-8")
        processor = BlueprintsProcessor(self.config)

        with closing(sqlite3.connect(":memory:")) as conn:
            processor.process_blueprints_to_db(processor.read_blueprints_jsonl(), conn.cursor())
            self.assertEqual(
                conn.execute(
                    "SELECT manufacturing_time, maxRunsPerCopy FROM blueprint_process_time "
                    "WHERE blueprintTypeID=683"
                ).fetchone(),
                (6000, 30),
            )
            self.assertEqual(
                conn.execute(
                    "SELECT typeID, quantity FROM blueprint_manufacturing_output "
                    "WHERE blueprintTypeID=683"
                ).fetchone(),
                (582, 1),
            )

    def test_invalid_blueprint_structure_raises(self):
        (self.sde / "blueprints.jsonl").write_text(
            json.dumps({"_key": 683, "activities": {}}), encoding="utf-8"
        )
        processor = BlueprintsProcessor(self.config)
        with self.assertRaisesRegex(SdeSchemaError, "maxProductionLimit"):
            processor.read_blueprints_jsonl()


class SkinMaterialCompatibilityTests(unittest.TestCase):
    def test_removed_skin_material_id_falls_back_to_key(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "sde.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "skinLicenses.jsonl",
                    json.dumps({"_key": 34599, "duration": -1, "skinID": 187}),
                )
                archive.writestr(
                    "skins.jsonl",
                    json.dumps({"_key": 187, "skinMaterialID": 2}),
                )
                archive.writestr(
                    "skinMaterials.jsonl",
                    json.dumps({"_key": 2, "materialSetID": 187}),
                )
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(read_skin_materials(archive), {34599: 187})


class FakeResponse:
    def __init__(self, status, payload=None, error=None):
        self.status = status
        self.headers = {}
        self.payload = payload
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def json(self):
        if self.error:
            raise self.error
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url):
        return self.responses.pop(0)


class LoyaltyStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.processor = LoyaltyStoresProcessor({
            "paths": {"db_output": "unused"},
            "languages": ["en"],
        })
        self.processor.max_retries = 2
        self.processor.retry_delay = 0

    async def test_missing_offers_are_optional(self):
        result = await self.processor.fetch_with_retry(
            FakeSession([FakeResponse(404)]),
            "https://example.test/offers",
            missing_ok=True,
        )
        self.assertIsNone(result)

    async def test_server_error_is_fatal_after_retries(self):
        with self.assertRaisesRegex(LoyaltyStoreError, "HTTP 503"):
            await self.processor.fetch_with_retry(
                FakeSession([FakeResponse(503), FakeResponse(503)]),
                "https://example.test/offers",
                missing_ok=True,
            )

    async def test_missing_corporation_list_is_fatal(self):
        with self.assertRaisesRegex(LoyaltyStoreError, "HTTP 404"):
            await self.processor.fetch_with_retry(
                FakeSession([FakeResponse(404)]),
                "https://example.test/corporations",
                missing_ok=False,
            )

    def test_offer_schema_error_is_not_silently_skipped(self):
        with self.assertRaisesRegex(LoyaltyStoreError, "offer_id/type_id"):
            self.processor.process_corporation_data(1000, [{"offer_id": 1}])

    def test_empty_offer_list_is_optional(self):
        self.assertIsNone(self.processor.process_corporation_data(1000, []))


if __name__ == "__main__":
    unittest.main()

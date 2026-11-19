import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from evesde.processors.dogma_effects_processor import (
    DogmaEffectsProcessor,
    load_effect_patches,
    modifier_info_sha256,
    validate_effect_patches,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTUAL_PATCHES = PROJECT_ROOT / "data" / "dogma_effect_patches.json"


RAW_MODIFIER_INFO = [{
    "domain": "shipID",
    "func": "ItemModifier",
    "modifiedAttributeID": 51,
    "modifyingAttributeID": 293,
    "operation": 2,
}]

PATCHED_MODIFIER_INFO = [{
    "domain": "shipID",
    "func": "LocationRequiredSkillModifier",
    "modifiedAttributeID": 51,
    "modifyingAttributeID": 293,
    "operation": 6,
    "skillTypeID": -1,
}]


class DogmaEffectPatchTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.cursor = self.db.cursor()
        self.cursor.executescript("""
            CREATE TABLE dogmaEffects (
                effect_id INTEGER PRIMARY KEY,
                effect_name TEXT,
                modifier_info TEXT
            );
            CREATE TABLE dogmaAttributes (attribute_id INTEGER PRIMARY KEY);
            CREATE TABLE groups (group_id INTEGER PRIMARY KEY);
            CREATE TABLE types (type_id INTEGER PRIMARY KEY);
            INSERT INTO dogmaAttributes VALUES (51), (293), (999);
        """)
        self.cursor.execute(
            "INSERT INTO dogmaEffects VALUES (1851, 'selfRof', ?)",
            (json.dumps(RAW_MODIFIER_INFO),),
        )
        self.processor = DogmaEffectsProcessor({"paths": {"sde_input": "."}})

    def tearDown(self):
        self.db.close()

    def patch(self, **overrides):
        patch = {
            "effect_id": 1851,
            "effect_name": "selfRof",
            "expected_modifier_info_sha256": modifier_info_sha256(RAW_MODIFIER_INFO),
            "modifier_info": PATCHED_MODIFIER_INFO,
        }
        patch.update(overrides)
        return [patch]

    def write_patches(self, patches):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "dogma_effect_patches.json"
        path.write_text(json.dumps(patches), encoding="utf-8")
        return path

    def test_valid_patch_is_applied(self):
        self.processor._apply_effect_patches(
            self.cursor, self.write_patches(self.patch())
        )
        value = self.cursor.execute(
            "SELECT modifier_info FROM dogmaEffects WHERE effect_id = 1851"
        ).fetchone()[0]
        self.assertEqual(json.loads(value), PATCHED_MODIFIER_INFO)

    def test_official_change_fails_instead_of_being_overwritten(self):
        patches = self.patch(expected_modifier_info_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "official modifier_info changed"):
            self.processor._apply_effect_patches(
                self.cursor, self.write_patches(patches)
            )
        value = self.cursor.execute(
            "SELECT modifier_info FROM dogmaEffects WHERE effect_id = 1851"
        ).fetchone()[0]
        self.assertEqual(json.loads(value), RAW_MODIFIER_INFO)

    def test_missing_official_modifier_can_be_filled(self):
        self.cursor.execute(
            "UPDATE dogmaEffects SET modifier_info = NULL WHERE effect_id = 1851"
        )
        patches = self.patch(
            expected_modifier_info_sha256=modifier_info_sha256(None)
        )
        self.processor._apply_effect_patches(
            self.cursor, self.write_patches(patches)
        )
        value = self.cursor.execute(
            "SELECT modifier_info FROM dogmaEffects WHERE effect_id = 1851"
        ).fetchone()[0]
        self.assertEqual(json.loads(value), PATCHED_MODIFIER_INFO)

    def test_missing_effect_fails(self):
        with self.assertRaisesRegex(ValueError, "matched 0"):
            validate_effect_patches(
                self.cursor, self.patch(effect_id=9999)
            )

    def test_missing_patch_file_fails(self):
        with self.assertRaises(FileNotFoundError):
            load_effect_patches(Path("/definitely/missing/dogma_effect_patches.json"))

    def test_unknown_attribute_reference_fails(self):
        bad = [{
            **PATCHED_MODIFIER_INFO[0],
            "modifiedAttributeID": 123456789,
        }]
        with self.assertRaisesRegex(ValueError, "unknown modified attribute"):
            validate_effect_patches(
                self.cursor, self.patch(modifier_info=bad)
            )

    def test_actual_manifest_only_fills_missing_official_modifiers(self):
        patches = load_effect_patches(ACTUAL_PATCHES)
        self.assertEqual(
            len({patch["effect_id"] for patch in patches}),
            len(patches),
            "effect_id must be unique",
        )
        self.assertEqual(
            len({patch["effect_name"] for patch in patches}),
            len(patches),
            "effect_name must be unique",
        )
        for patch in patches:
            self.assertEqual(
                patch["expected_modifier_info_sha256"],
                modifier_info_sha256(None),
                f"{patch['effect_name']} would overwrite official modifierInfo",
            )

    def test_actual_manifest_applies_to_official_empty_shape(self):
        patches = load_effect_patches(ACTUAL_PATCHES)
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        cursor = db.cursor()
        cursor.executescript("""
            CREATE TABLE dogmaEffects (
                effect_id INTEGER PRIMARY KEY,
                effect_name TEXT,
                modifier_info TEXT
            );
            CREATE TABLE dogmaAttributes (attribute_id INTEGER PRIMARY KEY);
            CREATE TABLE groups (group_id INTEGER PRIMARY KEY);
            CREATE TABLE types (type_id INTEGER PRIMARY KEY);
        """)

        attributes = set()
        groups = set()
        skills = set()
        for patch in patches:
            cursor.execute(
                "INSERT INTO dogmaEffects VALUES (?, ?, NULL)",
                (patch["effect_id"], patch["effect_name"]),
            )
            for modifier in patch["modifier_info"]:
                attributes.add(modifier["modifiedAttributeID"])
                attributes.add(modifier["modifyingAttributeID"])
                if modifier.get("groupID"):
                    groups.add(modifier["groupID"])
                if modifier.get("skillTypeID", 0) not in (0, -1):
                    skills.add(modifier["skillTypeID"])

        cursor.executemany(
            "INSERT INTO dogmaAttributes VALUES (?)",
            [(value,) for value in sorted(attributes)],
        )
        cursor.executemany(
            "INSERT INTO groups VALUES (?)",
            [(value,) for value in sorted(groups)],
        )
        cursor.executemany(
            "INSERT INTO types VALUES (?)",
            [(value,) for value in sorted(skills)],
        )

        self.processor._apply_effect_patches(cursor, ACTUAL_PATCHES)
        for patch in patches:
            value = cursor.execute(
                "SELECT modifier_info FROM dogmaEffects WHERE effect_id = ?",
                (patch["effect_id"],),
            ).fetchone()[0]
            self.assertEqual(json.loads(value), patch["modifier_info"])


if __name__ == "__main__":
    unittest.main()

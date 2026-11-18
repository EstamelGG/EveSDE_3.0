"""处理器失败必须向上传播，可选数据缺失才允许跳过。"""

import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from evesde.pipeline import execute_processor
from evesde.processors import categories_processor, dynamic_items_updater, types_processor


class ProcessorFailurePropagationTests(unittest.TestCase):
    def test_types_main_returns_inner_failure(self):
        with patch.object(types_processor, "TypesProcessor") as processor_type:
            processor_type.return_value.process_all_languages.return_value = False
            self.assertFalse(types_processor.main({}))

    def test_pipeline_turns_processor_failure_into_build_error(self):
        with patch.object(types_processor, "TypesProcessor") as processor_type:
            processor_type.return_value.process_all_languages.return_value = False
            with self.assertRaisesRegex(RuntimeError, "物品详情数据处理失败"):
                execute_processor(types_processor.main, "物品详情数据", {})

    def test_database_write_error_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {"paths": {"db_output": directory}}
            processor = object.__new__(categories_processor.CategoriesProcessor)
            processor.load_categories_data = Mock()

            failure = sqlite3.OperationalError("database is locked")
            with patch.object(categories_processor.sqlite3, "connect", return_value=Mock()):
                with patch.object(processor, "process_categories_to_db", side_effect=failure):
                    with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                        processor.update_all_databases(config)

    def test_missing_dynamic_item_data_fails_instead_of_skipping(self):
        with patch.object(dynamic_items_updater, "load_dynamic_items_from_sde", return_value={}):
            self.assertFalse(dynamic_items_updater.update_all_databases({"paths": {"db_output": "unused"}}))


if __name__ == "__main__":
    unittest.main()

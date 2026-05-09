import importlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class RagManagerStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "rag.sqlite3")
        self.legacy_path = os.path.join(self.temp_dir.name, "rag.json")
        os.environ["AUXILIUM_RAG_DB_PATH"] = self.db_path
        os.environ["AUXILIUM_LEGACY_RAG_JSON_PATH"] = self.legacy_path

    def tearDown(self):
        os.environ.pop("AUXILIUM_RAG_DB_PATH", None)
        os.environ.pop("AUXILIUM_LEGACY_RAG_JSON_PATH", None)
        self.temp_dir.cleanup()

    def _reload_module(self):
        import rag_manager

        return importlib.reload(rag_manager)

    def test_migrates_legacy_json_and_returns_structured_entries(self):
        with open(self.legacy_path, "w") as handle:
            json.dump(
                [
                    {
                        "type": "structured_gss",
                        "gss_name": "Legacy Station",
                        "latitude": 26.1,
                        "longitude": 72.5,
                    }
                ],
                handle,
            )

        rag_manager = self._reload_module()
        entries = rag_manager.retrieve_all_structured_gss_data()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["gss_name"], "Legacy Station")

    def test_feedback_round_trip_uses_sqlite_store(self):
        rag_manager = self._reload_module()

        with patch.object(rag_manager, "get_embedding", side_effect=[[1.0, 0.0], [1.0, 0.0]]):
            rag_manager.add_feedback("flat land", "prioritize low slope")
            results = rag_manager.retrieve_relevant_context("flat land", top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["correction"], "prioritize low slope")


if __name__ == "__main__":
    unittest.main()

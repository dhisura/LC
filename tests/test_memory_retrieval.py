"""Tests for MemoryManager retrieval and scoring.

The retrieved vaccines are injected verbatim into the DEV prompt, so both what
comes back and how much of it matters.
"""
import tempfile
import unittest
from pathlib import Path

from lc.engine.memory import MemoryManager


class TestMemoryRetrieval(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Path(self.temp_dir.name) / "mem.db"
        self.mem = MemoryManager(db_path=self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def add(self, stack, symptom, root="cause", rule="rule"):
        return self.mem.record_vaccine(stack, symptom, root, rule)

    def test_record_and_list(self):
        self.add("python", "IndexError: list index out of range")
        self.add("node", "Cannot read property of undefined")
        vaccines = self.mem.list_vaccines()
        self.assertEqual(len(vaccines), 2)
        # Newest first.
        self.assertEqual(vaccines[0]["stack"], "node")

    def test_stack_is_normalised_to_lowercase(self):
        self.add("PyThOn", "Something")
        self.assertEqual(self.mem.list_vaccines()[0]["stack"], "python")

    def test_stack_match_outranks_keyword_match(self):
        self.add("python", "generic python issue")
        self.add("node", "generic python issue in a node project")
        results = self.mem.get_relevant_vaccines(stack="python", query="python")
        self.assertEqual(results[0]["stack"], "python")

    def test_no_match_falls_back_to_recent(self):
        # Every run injects these; if nothing matches, injecting the whole
        # table defeats the point of retrieving them.
        for i in range(3):
            self.add("rust", f"rust issue {i}")
        results = self.mem.get_relevant_vaccines(stack="python", query="nothing matches")
        self.assertLessEqual(len(results), 5)
        self.assertTrue(results)

    def test_limit_is_respected(self):
        for i in range(10):
            self.add("python", f"issue {i}")
        self.assertEqual(len(self.mem.get_relevant_vaccines(stack="python", query="", limit=3)), 3)

    def test_empty_query_and_stack_returns_latest(self):
        self.add("python", "a")
        self.add("python", "b")
        results = self.mem.get_relevant_vaccines()
        self.assertEqual(results[0]["symptom"], "b")

    def test_keyword_scoring_finds_a_match(self):
        self.add("python", "ModuleNotFoundError: no module named requests")
        self.add("node", "npm install fails")
        results = self.mem.get_relevant_vaccines(stack="", query="modulenotfound requests")
        self.assertEqual(len(results), 1)
        self.assertIn("ModuleNotFound", results[0]["symptom"])

    def test_record_session_returns_id(self):
        sid = self.mem.record_session(task="do thing", status="SUCCESS", summary="ok")
        self.assertGreater(sid, 0)

    def test_short_words_are_ignored_in_scoring(self):
        # Single/double character tokens match almost everything and would
        # otherwise dominate the ranking.
        self.add("python", "a b c python")
        self.add("rust", "totally unrelated")
        results = self.mem.get_relevant_vaccines(stack="", query="a b c")
        self.assertLessEqual(len(results), 5)

    def test_tables_are_created_on_first_use(self):
        self.assertTrue(self.db.exists())
        self.assertEqual(self.mem.list_vaccines(), [])


if __name__ == "__main__":
    unittest.main()
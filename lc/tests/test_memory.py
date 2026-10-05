"""Unit tests for SQLite Memory Manager and Mistake Vaccine Engine."""
import tempfile
import unittest
from pathlib import Path
from lc.engine.memory import MemoryManager


class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_memory.db"
        self.mem = MemoryManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_and_retrieve_vaccine(self):
        # Record a vaccine
        vid = self.mem.record_vaccine(
            stack="python",
            symptom="ImportError: No module named 'rich'",
            root_cause="Missing dependency in virtual environment",
            prevention_rule="Always verify requirements or use standard library fallback"
        )
        self.assertGreater(vid, 0)

        # Retrieve vaccine by stack
        vacs = self.mem.get_relevant_vaccines(stack="python", query="import error rich")
        self.assertEqual(len(vacs), 1)
        self.assertEqual(vacs[0]["stack"], "python")
        self.assertIn("rich", vacs[0]["symptom"])

        # Test listing all vaccines
        all_vacs = self.mem.list_vaccines()
        self.assertEqual(len(all_vacs), 1)

    def test_record_session(self):
        sid = self.mem.record_session(
            task="Build CLI timer",
            status="SUCCESS",
            summary="Clean implementation with 100% test pass"
        )
        self.assertGreater(sid, 0)


if __name__ == "__main__":
    unittest.main()

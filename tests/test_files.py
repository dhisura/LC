"""Unit tests for FileManager and Anti-Overtime Diff Budget counting."""
import tempfile
import unittest
from pathlib import Path
from lc.tools.files import FileManager


class TestFileManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fm = FileManager(workspace=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_and_read_file(self):
        bytes_written, diff = self.fm.write_file("test.py", "print('hello')\n")
        self.assertGreater(bytes_written, 0)
        self.assertIn("[NEW FILE]", diff)

        content = self.fm.read_file("test.py")
        self.assertEqual(content, "print('hello')\n")

    def test_diff_budget_line_counter(self):
        self.fm.write_file("calc.py", "def add(a, b):\n    return a + b\n")
        bytes_written, diff = self.fm.write_file(
            "calc.py",
            "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
        )
        diff_lines = self.fm.count_diff_lines(diff)
        self.assertGreater(diff_lines, 0)


if __name__ == "__main__":
    unittest.main()

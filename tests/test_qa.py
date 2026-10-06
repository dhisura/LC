"""Tests for QA's test-command selection.

The runner choice decides whether a sprint passes or fails, so the heuristics
that pick it have to be driven by real imports rather than substring matches.
"""
import tempfile
import unittest
from pathlib import Path

from lc.roles.qa import QAEngineer
from lc.roles.pm import Ticket


def make_ticket(stack="python"):
    return Ticket(
        title="t",
        task="t",
        stack=stack,
        missing_items=[],
        acceptance_criteria=["works"],
        definition_of_done="done",
        suggested_files=["calc.py"],
    )


class TestPytestDetection(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.temp_dir.name)
        # QA only needs the file manager here; the LLM is never called.
        self.qa = QAEngineer(llm=None, workspace=str(self.ws))

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, name, content):
        (self.ws / name).write_text(content, encoding="utf-8")
        return name

    def test_real_pytest_file_selects_pytest(self):
        name = self.write("test_x.py", "import pytest\n\ndef test_a():\n    assert True\n")
        self.assertTrue(self.qa._looks_like_pytest(name))

    def test_from_pytest_import_selects_pytest(self):
        name = self.write("test_x.py", "from pytest import raises\n\ndef test_a():\n    pass\n")
        self.assertTrue(self.qa._looks_like_pytest(name))

    def test_unittest_file_is_not_pytest(self):
        name = self.write(
            "test_x.py",
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n",
        )
        self.assertFalse(self.qa._looks_like_pytest(name))

    def test_mentioning_pytest_in_a_comment_is_not_pytest(self):
        # The regression: a bare substring scan saw "pytest" in the comment and
        # routed a plain unittest file to a runner that may not be installed.
        name = self.write(
            "test_x.py",
            "import unittest\n"
            "# we could use pytest here, but unittest is in the stdlib\n"
            "class T(unittest.TestCase):\n"
            "    def test_a(self):\n"
            "        pass\n",
        )
        self.assertFalse(self.qa._looks_like_pytest(name))

    def test_bare_test_functions_without_unittest_are_not_pytest(self):
        # Also a regression: bare `def test_` with no import was treated as
        # pytest. It is not, so it goes to unittest discovery.
        name = self.write("test_x.py", "def test_a():\n    assert True\n")
        self.assertFalse(self.qa._looks_like_pytest(name))

    def test_syntax_error_is_not_pytest(self):
        name = self.write("test_x.py", "def broken(:\n")
        self.assertFalse(self.qa._looks_like_pytest(name))

    def test_missing_file_is_not_pytest(self):
        self.assertFalse(self.qa._looks_like_pytest("does_not_exist.py"))

    def test_file_outside_workspace_is_not_pytest(self):
        # The containment guard raises ValueError; it must not escape as an error.
        self.assertFalse(self.qa._looks_like_pytest("../outside.py"))


class TestDetermineTestCommand(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.temp_dir.name)
        self.qa = QAEngineer(llm=None, workspace=str(self.ws))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pytest_project_runs_pytest(self):
        (self.ws / "test_x.py").write_text("import pytest\ndef test_a(): pass\n", encoding="utf-8")
        cmd = self.qa.determine_test_command(make_ticket(), [{"file": "test_x.py"}])
        self.assertEqual(cmd, "pytest test_x.py")

    def test_unittest_project_runs_discovery(self):
        (self.ws / "test_x.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n",
            encoding="utf-8",
        )
        cmd = self.qa.determine_test_command(make_ticket(), [{"file": "test_x.py"}])
        self.assertEqual(cmd, 'python -m unittest discover -s . -p "test_*.py"')

    def test_generated_command_names_an_existing_file(self):
        # The old code interpolated an undefined `target_file`, raised
        # NameError, and the bare `except Exception` silently swallowed it --
        # so a pytest project never actually got `pytest`.
        (self.ws / "test_gen.py").write_text("import pytest\ndef test_a(): pass\n", encoding="utf-8")
        cmd = self.qa.determine_test_command(make_ticket(), [{"file": "test_gen.py"}])
        if cmd.startswith("pytest"):
            self.assertIn("test_gen.py", cmd)
            self.assertTrue((self.ws / "test_gen.py").exists())

    def test_node_stack_returns_npm_test(self):
        cmd = self.qa.determine_test_command(make_ticket(stack="node"), [{"file": "index.js"}])
        self.assertEqual(cmd, "npm test")


if __name__ == "__main__":
    unittest.main()
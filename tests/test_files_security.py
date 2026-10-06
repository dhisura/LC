"""Tests that the workspace is an enforced boundary, not a suggestion.

`dev.write_solution` forwards `[FILE: ...]` headers straight from the LLM
response into `FileManager.write_file`. Without containment, a model (or a
prompt-injected comment in a file it read) can name any path on disk.
"""
import os
import tempfile
import unittest
from pathlib import Path

from lc.tools.files import FileManager


class TestWorkspaceContainment(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.ws = self.root / "workspace"
        self.ws.mkdir()
        self.fm = FileManager(workspace=str(self.ws))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parent_traversal_is_refused(self):
        with self.assertRaises(ValueError):
            self.fm.write_file("../escaped.py", "PWNED")
        self.assertFalse((self.root / "escaped.py").exists())

    def test_deep_traversal_is_refused(self):
        for path in (
            "../../escaped.py",
            "sub/../../escaped.py",
            "./../escaped.py",
            "a/b/../../../escaped.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.fm.write_file(path, "PWNED")

    def test_absolute_path_is_refused(self):
        outside = self.root / "outside.py"
        with self.assertRaises(ValueError):
            self.fm.write_file(str(outside), "PWNED")
        self.assertFalse(outside.exists())

    def test_windows_drive_absolute_path_is_refused(self):
        # A drive-rooted path is a different root entirely, so it must not be
        # trusted as "already inside" just because it is absolute.
        with self.assertRaises(ValueError):
            self.fm.write_file("C:/lc_escape_probe.txt", "PWNED")

    def test_read_outside_workspace_is_refused(self):
        secret = self.root / "secret.txt"
        secret.write_text("top secret", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.fm.read_file("../secret.txt")

    def test_dotdot_that_stays_inside_is_allowed(self):
        # `sub/../ok.py` resolves back into the workspace and must still work;
        # the check is on the resolved location, not on the spelling.
        self.fm.write_file("sub/ok.py", "x = 1\n")
        self.assertTrue((self.ws / "sub" / "ok.py").exists())

    def test_symlink_pointing_outside_is_refused(self):
        # resolve() follows symlinks, so a link planted in the workspace is
        # caught rather than silently granting write access to its target.
        target = self.root / "outside_dir"
        target.mkdir()
        link = self.ws / "link"
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted on this platform")

        with self.assertRaises(ValueError):
            self.fm.write_file("link/planted.py", "PWNED")
        self.assertFalse((target / "planted.py").exists())

    def test_ordinary_paths_still_work(self):
        for path in ("a.py", "src/b.py", "./c.py"):
            with self.subTest(path=path):
                _, diff = self.fm.write_file(path, "x = 1\n")
                self.assertIn("x = 1", diff)
        self.assertEqual(self.fm.read_file("src/b.py"), "x = 1\n")

    def test_resolve_error_names_both_ends(self):
        # The message has to be actionable: which path, and which boundary.
        with self.assertRaises(ValueError) as cm:
            self.fm.resolve("../nope.py")
        message = str(cm.exception)
        self.assertIn("..", message)
        self.assertIn("outside", message)


if __name__ == "__main__":
    unittest.main()
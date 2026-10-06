"""Tests for the DEV role's output parsing.

The `[FILE: ...]` headers and the paths inside them come from the LLM, so this
is the boundary where an untrusted string becomes a filesystem write.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lc.roles.dev import Developer
from lc.roles.pm import Ticket


def make_ticket(suggested_files=None):
    return Ticket(
        title="t",
        task="t",
        stack="python",
        missing_items=[],
        acceptance_criteria=["works"],
        definition_of_done="done",
        suggested_files=suggested_files or ["calc.py"],
    )


class TestDevParsing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.temp_dir.name)
        self.dev = Developer(llm=None, console=mock.MagicMock(), workspace=str(self.ws))
        self.ticket = make_ticket()

    def tearDown(self):
        self.temp_dir.cleanup()

    def stub_output(self, text):
        self.dev.generate = mock.MagicMock(return_value=text)

    def test_parses_two_files(self):
        self.stub_output(
            "[FILE: a.py]\n```python\nx = 1\n```\n[END FILE]\n"
            "[FILE: b.py]\n```python\ny = 2\n```\n[END FILE]"
        )
        results = self.dev.write_solution(self.ticket)
        self.assertEqual([r["file"] for r in results], ["a.py", "b.py"])
        self.assertTrue((self.ws / "a.py").exists())
        self.assertTrue((self.ws / "b.py").exists())

    def test_traversal_path_is_refused_but_other_files_survive(self):
        # The regression: a traversal path raised ValueError out of
        # write_file and aborted the whole sprint, losing good work.
        self.stub_output(
            "[FILE: ../../escaped.py]\n```python\nPWNED\n```\n[END FILE]\n"
            "[FILE: good.py]\n```python\nok = True\n```\n[END FILE]"
        )
        results = self.dev.write_solution(self.ticket)

        self.assertEqual([r["file"] for r in results], ["good.py"])
        self.assertFalse((self.ws.parent / "escaped.py").exists())
        self.assertTrue((self.ws / "good.py").exists())

    def test_absolute_path_is_refused(self):
        self.stub_output(
            "[FILE: C:/lc_dev_escape_probe.txt]\n```\nPWNED\n```\n[END FILE]\n"
            "[FILE: good.py]\n```\nok = True\n```\n[END FILE]"
        )
        results = self.dev.write_solution(self.ticket)
        self.assertEqual([r["file"] for r in results], ["good.py"])

    def test_all_files_refused_falls_back_without_crashing(self):
        # The traversal file is refused; the fallback then writes the whole raw
        # response to suggested_files[0], which is in-workspace. The point is
        # that a refused path neither escapes nor aborts the sprint.
        escaped = self.ws.parent / "escaped_marker.py"
        self.stub_output(f"[FILE: ../{escaped.name}]\n```\nx\n```\n[END FILE]")
        results = self.dev.write_solution(self.ticket)

        self.assertFalse(escaped.exists())
        for record in results:
            target = (self.ws / record["file"]).resolve()
            self.assertTrue(str(target).startswith(str(self.ws)))
            self.assertTrue(target.exists())

    def test_fence_lines_are_stripped_from_the_written_file(self):
        """Markdown fences are delimiters, not content.

        A bare ``` inside the code is indistinguishable from a closing fence in
        any markdown parser, so fenced output is written with the fence lines
        removed. Code that needs a literal ``` has to use a longer outer fence
        (~~~~), which the model prompt should request.
        """
        self.stub_output(
            '[FILE: readme.py]\n```python\nDOC = """\ninner\n"""\n```\n[END FILE]'
        )
        results = self.dev.write_solution(self.ticket)
        self.assertEqual(len(results), 1)
        content = (self.ws / "readme.py").read_text(encoding="utf-8")
        self.assertNotIn("```", content)
        self.assertIn("inner", content)

    def test_info_string_fence_only_opens(self):
        # ```python opens; a following bare ``` closes. An opener cannot be
        # confused with a closer, so this pair round-trips.
        self.stub_output("[FILE: a.py]\n```python\nx = 1\n```\n[END FILE]")
        results = self.dev.write_solution(self.ticket)
        self.assertEqual(len(results), 1)
        content = (self.ws / "a.py").read_text(encoding="utf-8")
        self.assertEqual(content.strip(), "x = 1")

    def test_tilde_fence_protects_backticks_in_content(self):
        # The model is told to use ~~~~ when the code contains ```. Honour it,
        # otherwise that instruction is a lie and Markdown templates still break.
        self.stub_output(
            "[FILE: readme.py]\n~~~~python\n"
            'DOC = """\n```bash\necho hi\n```\n"""\n'
            "~~~~\n[END FILE]"
        )
        results = self.dev.write_solution(self.ticket)
        self.assertEqual(len(results), 1)
        content = (self.ws / "readme.py").read_text(encoding="utf-8")
        self.assertIn("```bash", content)
        self.assertIn("echo hi", content)
        self.assertNotIn("~~~~", content)

    def test_nested_path_creates_parent_dirs(self):
        self.stub_output("[FILE: src/pkg/deep.py]\n```\nx = 1\n```\n[END FILE]")
        results = self.dev.write_solution(self.ticket)
        self.assertEqual(len(results), 1)
        self.assertTrue((self.ws / "src" / "pkg" / "deep.py").exists())

    def test_diff_lines_are_counted(self):
        self.stub_output("[FILE: a.py]\n```\n1\n2\n3\n```\n[END FILE]")
        results = self.dev.write_solution(self.ticket)
        self.assertEqual(results[0]["diff_lines"], 3)


if __name__ == "__main__":
    unittest.main()
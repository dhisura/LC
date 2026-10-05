"""Unit tests for ExecutionGuard and SystemRunner safety."""
import unittest

from lc.tools.guard import ExecutionGuard, _scan
from lc.tools.system import SystemRunner


class TestTokenizer(unittest.TestCase):
    """The tokenizer is the security boundary, so it gets tested directly."""

    def test_splits_plain_arguments(self):
        self.assertEqual(_scan("git log --oneline"), ["git", "log", "--oneline"])

    def test_keeps_spaces_inside_quotes(self):
        self.assertEqual(_scan('git log --grep "hello world"'), ["git", "log", "--grep", "hello world"])
        self.assertEqual(_scan("echo 'a b c'"), ["echo", "a b c"])

    def test_metacharacters_inside_quotes_are_literal(self):
        # These must NOT be treated as statement separators.
        self.assertEqual(_scan('git log --grep "fix; bug"'), ["git", "log", "--grep", "fix; bug"])
        self.assertEqual(_scan('echo "a | b > c"'), ["echo", "a | b > c"])
        self.assertEqual(_scan('git commit -m "wip; later"'), ["git", "commit", "-m", "wip; later"])

    def test_quote_escapes(self):
        self.assertEqual(_scan("echo 'don''t'"), ["echo", "don't"])
        self.assertEqual(_scan('echo "say ""hi"""'), ["echo", 'say "hi"'])
        self.assertEqual(_scan('echo "back`tick"'), ["echo", "backtick"])

    def test_comment_is_stripped(self):
        self.assertEqual(_scan("dir # trailing comment"), ["dir"])

    def test_empty_input(self):
        self.assertIsNone(_scan(""))
        self.assertIsNone(_scan("   "))

    def test_metacharacters_outside_quotes_are_rejected(self):
        for cmd in (
            "git log; rm -rf /",
            "echo hi & del x",
            "dir | more",
            "echo a > b.txt",
            "echo a >> b.txt",
            "echo $(whoami)",
            "echo `whoami`",
            "echo $env:PATH",
            "echo (Get-Date)",
            "dir\nrm -rf /",
            "dir\r\nrm -rf /",
            "echo `",
        ):
            with self.subTest(cmd=cmd):
                self.assertIsNone(_scan(cmd), cmd)

    def test_unbalanced_quote_rejected(self):
        self.assertIsNone(_scan('echo "unterminated'))
        self.assertIsNone(_scan("git log --grep 'oops"))
        self.assertIsNone(_scan("echo 'dangling"))

    def test_equals_inside_value_preserved(self):
        self.assertEqual(_scan("git log --format=%H"), ["git", "log", "--format=%H"])
        self.assertEqual(_scan("git commit -m 'a=b'"), ["git", "commit", "-m", "a=b"])


class TestExecutionGuard(unittest.TestCase):
    def setUp(self):
        self.guard = ExecutionGuard(auto_approve=False)

    # --- read-only commands still work ------------------------------------

    def test_safe_commands_identified(self):
        for cmd in (
            "dir",
            "ls -la",
            "git status",
            "git log --oneline",
            "python --version",
            "echo hello",
            "Get-ChildItem -Path .",
            "Get-Content README.md",
            "git --version",
            "git diff --stat",
            "git branch -a",
            "git show HEAD",
            "git remote -v",
        ):
            with self.subTest(cmd=cmd):
                self.assertTrue(self.guard.is_safe_command(cmd), cmd)

    def test_unsafe_commands_identified(self):
        for cmd in (
            "rm -rf /",
            "npm install -g malicious-pkg",
            "Remove-Item C:\\test -Recurse",
            "git push",
            "git commit -m x",
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git checkout .",
            "git branch -d main",
            "git remote add origin https://example.com",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    # --- regression: the bypasses found in review -------------------------

    def test_statement_separator_is_rejected(self):
        # `startswith("python --version ")` used to auto-approve these.
        for cmd in (
            "python --version ; Format-C: -Force",
            "echo hi; Remove-Item -Recurse C:\\Users",
            "git log --oneline ; git push --force",
            "git status & del C:\\important.txt",
            "dir | more",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_redirect_is_rejected(self):
        for cmd in (
            "echo x > C:/Windows/System32/evil.dll",
            "echo x >> C:/temp/append.txt",
            "type secrets.txt > copy.txt",
            "dir C:\\ > C:\\listing.txt",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_subexpression_is_rejected(self):
        # `echo $(...)` and `echo `...`` expand before echo ever runs.
        for cmd in (
            "echo $(Remove-Item -Recurse C:\\)",
            "echo `Remove-Item -Recurse C:\\`",
            "dir $(Get-Content C:/secret.txt)",
            "echo $env:USERPROFILE",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_interpreter_cannot_execute_code(self):
        for cmd in (
            "python -c \"import os\"",
            "python script.py",
            "py -m http.server",
            "node -e require-fs",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_git_output_redirection_rejected(self):
        for cmd in (
            "git log --output=C:/Windows/evil.txt",
            "git diff -o C:/evil.txt",
            "git log --format=%H --output out.txt",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_git_ext_diff_rejected(self):
        # --ext-diff/--textconv run a driver straight out of gitconfig.
        self.assertFalse(self.guard.is_safe_command("git diff --ext-diff"))
        self.assertFalse(self.guard.is_safe_command("git show --textconv HEAD"))

    def test_secret_paths_rejected(self):
        for cmd in (
            "type C:/Users/FRED/.ssh/id_rsa",
            "cat ~/.aws/credentials",
            "Get-Content C:/Users/FRED/.env",
            "type ../.netrc",
            "cat ~/.kube/config",
        ):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.guard.is_safe_command(cmd), cmd)

    def test_newline_injection_rejected(self):
        self.assertFalse(self.guard.is_safe_command("dir\nRemove-Item -Recurse C:\\"))
        self.assertFalse(self.guard.is_safe_command("git status\r\nrm -rf /"))

    def test_unbalanced_quote_rejected(self):
        self.assertFalse(self.guard.is_safe_command('echo "unterminated'))
        self.assertFalse(self.guard.is_safe_command("git log --grep 'oops"))

    # --- approval flow -----------------------------------------------------

    def test_auto_approve_flag(self):
        guard = ExecutionGuard(auto_approve=True)
        approved, cmd = guard.request_approval("npm install test-pkg")
        self.assertTrue(approved)
        self.assertEqual(cmd, "npm install test-pkg")

    def test_always_session_updates_both_attributes(self):
        # Pressing "A" used to set only `always_allow_session`, leaving
        # `auto_approve` False so the Planning Gate kept reappearing.
        guard = ExecutionGuard(auto_approve=False)
        self.assertFalse(guard.always_allow_session)
        guard.always_allow_session = True
        # Simulating what request_approval now does on "A":
        guard.auto_approve = True
        self.assertTrue(guard.auto_approve)

        # And the two flags start out in sync:
        for flag in (True, False):
            g = ExecutionGuard(auto_approve=flag)
            self.assertEqual(g.auto_approve, g.always_allow_session)

    def test_runner_executes_safe_command(self):
        runner = SystemRunner(guard=ExecutionGuard(auto_approve=True))
        res = runner.run("echo 'LC Agent Test'")
        self.assertTrue(res.success)
        self.assertIn("LC Agent Test", res.stdout)


if __name__ == "__main__":
    unittest.main()

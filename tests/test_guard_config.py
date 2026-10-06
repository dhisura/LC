"""Tests for the per-project guard allowlist configuration.

The point of `LC_GUARD_EXTRA_*` is to widen the allowlist for a project's own
tools without running with `--yes`. These assert that it widens, and just as
importantly that it cannot widen the things it must never allow.

The guard unions the config at import time, so each test reloads the module
with the environment patched, then restores it.
"""
import importlib
import os
import unittest
from unittest import mock


class TestExtraAllowlist(unittest.TestCase):
    def setUp(self):
        import lc.config
        import lc.tools.guard
        self._config_mod = lc.config
        self._guard_mod = lc.tools.guard
        # Snapshot the real environment so reloads do not leak into other tests.
        self._env_keys = (
            "LC_GUARD_EXTRA_SAFE_COMMANDS",
            "LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS",
            "LC_GUARD_EXTRA_SENSITIVE_MARKERS",
        )
        self._saved = {k: os.environ.get(k) for k in self._env_keys}

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(self._config_mod)
        importlib.reload(self._guard_mod)

    def reload_guard(self, **env):
        """Reload config then guard with `env` applied, returning the guard class."""
        for key in self._env_keys:
            os.environ.pop(key, None)
        for key, value in env.items():
            os.environ[key] = value

        importlib.reload(self._config_mod)
        return importlib.reload(self._guard_mod).ExecutionGuard

    def test_extra_command_is_auto_approved(self):
        Guard = self.reload_guard(LC_GUARD_EXTRA_SAFE_COMMANDS="npm, npx")
        self.assertTrue(Guard().is_safe_command("npm --version"))

    def test_extra_git_subcommand_is_auto_approved(self):
        Guard = self.reload_guard(LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS="whatchanged")
        self.assertTrue(Guard().is_safe_command("git whatchanged"))

    def test_mutating_git_subcommands_still_cannot_be_added(self):
        # The allowlist unions into the read-only set but subtracts a denylist
        # last, so naming a mutating subcommand here must have no effect.
        # Without the denylist, `LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS=push`
        # put `git push` on the silent path.
        for subcommand in (
            "push", "commit", "reset", "clean", "add", "stage", "merge",
            "rebase", "checkout", "switch", "restore", "stash", "tag",
            "init", "pull", "fetch", "mv", "revert", "cherry-pick",
        ):
            with self.subTest(subcommand=subcommand):
                Guard = self.reload_guard(
                    LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS=subcommand
                )
                self.assertFalse(Guard().is_safe_command(f"git {subcommand}"))

    def test_denied_subcommand_cannot_be_smuggled_alongside_one(self):
        # An allowlisted subcommand must not carry a mutating sibling through.
        Guard = self.reload_guard(LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS="whatchanged")
        guard = Guard()
        self.assertTrue(guard.is_safe_command("git whatchanged"))
        self.assertFalse(guard.is_safe_command("git whatchanged push"))
        self.assertFalse(guard.is_safe_command("git whatchanged --output=/tmp/x"))

    def test_chaining_still_requires_approval_for_added_commands(self):
        # An added command is still subject to the metacharacter check.
        Guard = self.reload_guard(LC_GUARD_EXTRA_SAFE_COMMANDS="npm")
        guard = Guard()
        self.assertFalse(guard.is_safe_command("npm run build; Remove-Item -Recurse ."))
        self.assertFalse(guard.is_safe_command("npm run build > out.txt"))

    def test_extra_sensitive_marker_blocks_reads(self):
        Guard = self.reload_guard(
            LC_GUARD_EXTRA_SENSITIVE_MARKERS="myproject-secrets"
        )
        guard = Guard()
        self.assertFalse(guard.is_safe_command("type myproject-secrets/token.txt"))
        # And the built-in markers still apply.
        self.assertFalse(guard.is_safe_command("type .env"))

    def test_empty_config_changes_nothing(self):
        Guard = self.reload_guard()
        guard = Guard()
        self.assertTrue(guard.is_safe_command("git status"))
        self.assertFalse(guard.is_safe_command("git push"))


if __name__ == "__main__":
    unittest.main()
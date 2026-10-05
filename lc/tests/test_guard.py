"""Unit tests for ExecutionGuard and SystemRunner safety."""
import unittest
from lc.tools.guard import ExecutionGuard
from lc.tools.system import SystemRunner


class TestExecutionGuard(unittest.TestCase):
    def test_safe_commands_identified(self):
        guard = ExecutionGuard(auto_approve=False)
        self.assertTrue(guard.is_safe_command("dir"))
        self.assertTrue(guard.is_safe_command("ls -la"))
        self.assertTrue(guard.is_safe_command("git status"))
        self.assertTrue(guard.is_safe_command("python --version"))
        self.assertFalse(guard.is_safe_command("rm -rf /"))
        self.assertFalse(guard.is_safe_command("npm install -g malicious-pkg"))
        self.assertFalse(guard.is_safe_command("Remove-Item C:\\test -Recurse"))

    def test_auto_approve_flag(self):
        guard = ExecutionGuard(auto_approve=True)
        approved, cmd = guard.request_approval("npm install test-pkg")
        self.assertTrue(approved)
        self.assertEqual(cmd, "npm install test-pkg")

    def test_runner_executes_safe_command(self):
        runner = SystemRunner(guard=ExecutionGuard(auto_approve=True))
        res = runner.run("echo 'LC Agent Test'")
        self.assertTrue(res.success)
        self.assertIn("LC Agent Test", res.stdout)


if __name__ == "__main__":
    unittest.main()

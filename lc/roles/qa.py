"""QA Verification Engineer Role.
Runs real PowerShell test executions, checks runtime errors, and manages the Fail-Fast loop.
"""
from dataclasses import dataclass
import ast
from typing import List, Dict, Any, Optional
from lc.roles.base import BaseRole
from lc.roles.pm import Ticket
from lc.tools.system import SystemRunner, CommandResult
from lc.tools.files import FileManager
from lc.config import MAX_QA_RETRIES


@dataclass
class QAResult:
    success: bool
    command: str
    output: str
    exit_code: int
    attempt: int
    error_summary: str = ""


class QAEngineer(BaseRole):
    """The skeptical verification engineer who actually runs the code and tests."""

    def __init__(self, llm, runner=None, console=None, workspace="."):
        system_prompt = (
            "You are the Lead QA Engineer at LC (LazyCorp). You do not take the developer's word for it. "
            "You verify everything by executing real tests and inspecting exit codes.\n"
            "If a test fails, you isolate the exact error message and root cause so the dev can fix it immediately.\n"
            "You fail fast—if something is broken, you don't spin in loops, you diagnose cleanly."
        )
        super().__init__(name="QA", title="Verification Engineer", system_prompt=system_prompt, llm=llm, console=console)
        self.workspace = workspace
        self.runner = runner or SystemRunner()
        self.file_manager = FileManager(workspace)

    def _looks_like_pytest(self, test_file: str) -> bool:
        """True if `test_file` genuinely uses pytest rather than unittest.

        The previous check was a substring scan for "pytest" over the whole file,
        which misfired twice over: a comment mentioning pytest routed a plain
        unittest file to a runner that may not be installed, and a real pytest
        file that merely used bare `def test_...` functions without importing
        anything was sent to unittest, which cannot collect them. Matching the
        import, or pytest-only constructs, avoids both.
        """
        try:
            content = self.file_manager.read_file(test_file)
        except (OSError, ValueError):
            # Unreadable (or now out-of-bounds) -- fall through to unittest
            # discovery rather than guessing at a runner.
            return False

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            # import pytest / from pytest import ...
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "pytest" for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "pytest":
                    return True

        # pytest-only constructs that unittest cannot collect anyway.
        return any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("raises", "warns", "approx", "fixture", "mark")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
            for node in ast.walk(tree)
        )

    def determine_test_command(self, ticket: Ticket, dev_files: List[Dict[str, Any]]) -> str:
        """Determines the appropriate test or execution command."""
        file_names = [d["file"] for d in dev_files]
        
        # Check for explicit test files
        test_files = [f for f in file_names if "test" in f.lower()]
        
        if ticket.stack == "python":
            target_test = None
            if test_files:
                target_test = test_files[0]
            else:
                # Look for existing tests in workspace
                existing = self.file_manager.list_files(max_depth=2)
                existing_tests = [f for f in existing if "test" in f.lower() and f.endswith(".py")]
                if existing_tests:
                    target_test = existing_tests[0]

            if target_test:
                # Inspect if test file uses pytest syntax
                if self._looks_like_pytest(target_test):
                    return f"pytest {target_test}"
                # `python -m unittest path/to/test_x.py` only works when the file
                # is importable as a module: a bare `from calc import ...` inside
                # it needs the test's own directory on sys.path, and a
                # directory path is not a module name. Discovery run from the
                # workspace root handles both cases.
                return "python -m unittest discover -s . -p \"test_*.py\""

            # Default to running the main file as a syntax/runtime sanity check
            main_file = file_names[0] if file_names else "main.py"
            return f"python {main_file} --help"
            
        elif ticket.stack == "node":
            return "npm test"
        
        return "dir"

    def verify_solution(
        self,
        ticket: Ticket,
        dev_files: List[Dict[str, Any]],
        attempt: int = 1
    ) -> QAResult:
        """Executes verification and returns QAResult."""
        cmd = self.determine_test_command(ticket, dev_files)
        
        self.console.print_role_message(
            "QA",
            f"Executing automated verification (Attempt {attempt}/{MAX_QA_RETRIES + 1}):\n`{cmd}`",
            subtitle="Runtime Verification"
        )

        res: CommandResult = self.runner.run(
            cmd,
            cwd=self.workspace,
            role="QA",
            reason=f"Running automated verification for {ticket.title}"
        )

        if res.success:
            self.console.print_role_message(
                "QA",
                f"[PASS] ALL CHECKS PASSED (Exit Code: 0, Duration: {res.duration}s)\n\n```text\n{res.stdout[:500]}\n```",
                subtitle="Verification Passed"
            )
            return QAResult(
                success=True,
                command=cmd,
                output=res.stdout,
                exit_code=res.exit_code,
                attempt=attempt
            )
        else:
            # Analyze error
            err_log = res.output
            error_prompt = f"""
Command: {cmd}
Exit Code: {res.exit_code}
Output / Error:
{err_log[:1500]}

Provide a 2-line diagnostic:
1. Root cause
2. Recommended minimal fix
"""
            diagnostic = self.generate(error_prompt, temperature=0.1)
            self.console.print_role_message(
                "QA",
                f"[FAIL] VERIFICATION FAILED (Exit Code: {res.exit_code})\n\n"
                f"**Diagnostics**:\n{diagnostic}\n\n"
                f"**Raw Error**:\n```text\n{err_log[:400]}\n```",
                subtitle="Verification Failed"
            )
            return QAResult(
                success=False,
                command=cmd,
                output=err_log,
                exit_code=res.exit_code,
                attempt=attempt,
                error_summary=diagnostic
            )

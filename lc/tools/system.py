"""System execution tools for Windows PowerShell with guard integration."""
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from lc.config import COMMAND_TIMEOUT
from lc.tools.guard import ExecutionGuard


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    executed: bool
    denied: bool = False

    @property
    def success(self) -> bool:
        return self.executed and self.exit_code == 0

    @property
    def output(self) -> str:
        out = (self.stdout + "\n" + self.stderr).strip()
        return out if out else "(No output)"


class SystemRunner:
    """Executes system and terminal commands on Windows with safety checks."""

    def __init__(self, guard: Optional[ExecutionGuard] = None):
        self.guard = guard or ExecutionGuard()

    def run(
        self,
        command: str,
        cwd: str = ".",
        role: str = "Agent",
        reason: str = "",
        timeout: int = COMMAND_TIMEOUT
    ) -> CommandResult:
        """Runs a command via PowerShell after passing through safety guard."""
        approved, effective_cmd = self.guard.request_approval(command, role=role, reason=reason)
        if not approved:
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr="Command execution was denied by the user via ExecutionGuard.",
                duration=0.0,
                executed=False,
                denied=True
            )

        start_time = time.time()
        try:
            # Run via Windows PowerShell
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", effective_cmd],
                cwd=str(Path(cwd).resolve()),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            duration = round(time.time() - start_time, 2)
            return CommandResult(
                command=effective_cmd,
                exit_code=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                duration=duration,
                executed=True
            )
        except subprocess.TimeoutExpired:
            duration = round(time.time() - start_time, 2)
            return CommandResult(
                command=effective_cmd,
                exit_code=-2,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds.",
                duration=duration,
                executed=True
            )
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return CommandResult(
                command=effective_cmd,
                exit_code=-3,
                stdout="",
                stderr=f"Failed to execute command: {str(e)}",
                duration=duration,
                executed=False
            )

"""Execution Guard & Permission Interceptor for Windows system actions."""
import sys
from typing import Tuple
from lc.config import SAFE_COMMAND_PREFIXES


class ExecutionGuard:
    """Guards execution by intercepting potentially modifying commands."""

    def __init__(self, auto_approve: bool = False):
        self.always_allow_session = auto_approve
        self.auto_approve = auto_approve

    def is_safe_command(self, cmd: str) -> bool:
        """Check if command is purely read-only and safe to run silently."""
        stripped = cmd.strip().lower()
        for prefix in SAFE_COMMAND_PREFIXES:
            if stripped == prefix or stripped.startswith(prefix + " "):
                return True
        return False

    def request_approval(self, command: str, role: str = "Agent", reason: str = "") -> Tuple[bool, str]:
        """Intercepts command and prompts user for approval if needed.
        
        Returns:
            (approved: bool, effective_command: str)
        """
        if self.always_allow_session:
            return True, command

        if self.is_safe_command(command):
            return True, command

        # Prompt user in terminal
        print(f"\n\033[1;33m⚠️  [GUARD INTERCEPT]\033[0m \033[1m{role}\033[0m wants to execute:")
        print(f"   \033[36mCommand:\033[0m {command}")
        if reason:
            print(f"   \033[90mReason:  {reason}\033[0m")

        try:
            choice = input("   \033[1;32m[Y]\033[0mes once | \033[1;34m[A]\033[0mlways session | \033[1;31m[N]\033[0mo deny | \033[1;35m[C]\033[0mustom: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\033[31mAction cancelled by user.\033[0m")
            return False, command

        if choice in ("y", ""):
            return True, command
        elif choice == "a":
            self.always_allow_session = True
            print("\033[32m✔ Session permissions set to: Always Approve.\033[0m")
            return True, command
        elif choice == "c":
            custom_cmd = input("   Enter replacement command: ").strip()
            if custom_cmd:
                return True, custom_cmd
            return False, command
        else:
            print("\033[31m✖ Command execution denied.\033[0m")
            return False, command

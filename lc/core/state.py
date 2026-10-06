"""Authoritative Agent State and Lifecycle Modes for LC."""

from dataclasses import dataclass, field, asdict
from enum import Enum
import time
from typing import Any, Dict, Optional


class AgentMode(str, Enum):
    """Controlled lifecycle modes for the agent."""
    IDLE = "idle"
    PLANNING = "planning"
    WAITING_PERMISSION = "waiting_permission"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionLevel:
    """Permission tiers an operation must meet or exceed.

    `AgentState.permission_level` was a field nobody ever wrote to. These
    constants give it meaning: a mode implies a tier, and a command is only
    auto-approved when the active tier covers it.
    """
    OBSERVE = 0  # read-only inspection
    READ = 1     # read files
    WRITE = 2    # create or modify files
    DESTRUCTIVE = 3  # delete, force-push, publish


# The tier each mode is allowed to reach. EXECUTING is the only mode that
# writes files, and it is entered only after a permission gate in the CLI.
MODE_PERMISSION = {
    AgentMode.IDLE: PermissionLevel.OBSERVE,
    AgentMode.PLANNING: PermissionLevel.READ,
    AgentMode.WAITING_PERMISSION: PermissionLevel.READ,
    AgentMode.EXECUTING: PermissionLevel.WRITE,
    AgentMode.VERIFYING: PermissionLevel.WRITE,
    AgentMode.COMPLETED: PermissionLevel.OBSERVE,
    AgentMode.FAILED: PermissionLevel.OBSERVE,
    AgentMode.CANCELLED: PermissionLevel.OBSERVE,
}


@dataclass
class AgentState:
    """Single Source of Truth for the agent's live runtime state.
    
    Attributes:
        task: Current goal or instruction assigned to the agent.
        mode: Authoritative lifecycle mode (AgentMode).
        activity: High-level descriptive activity (e.g., 'analyzing_files', 'running_tests').
        active_app: Focused application if known (e.g., 'EXCEL.EXE', 'terminal').
        permission_level: Active required permission tier (0: observe, 1: read, 2: write, 3: destructive).
        progress: Task completion fraction from 0.0 to 1.0.
        confidence: Agent's confidence assessment from 0.0 to 1.0.
        error: Error message or traceback if the state is FAILED.
        created_at: Epoch timestamp when the state was initialized.
        updated_at: Epoch timestamp when the state was last modified.
    """
    task: str = ""
    mode: AgentMode = AgentMode.IDLE
    activity: str = ""
    active_app: Optional[str] = None
    permission_level: int = 0
    progress: float = 0.0
    confidence: float = 1.0
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def transition(
        self,
        mode: AgentMode,
        activity: Optional[str] = None,
        error: Optional[str] = None,
        progress: Optional[float] = None,
        confidence: Optional[float] = None,
        active_app: Optional[str] = None,
        permission_level: Optional[int] = None,
    ) -> "AgentState":
        """Controlled state transition mutating timestamps and attributes."""
        if not isinstance(mode, AgentMode):
            raise ValueError(f"Invalid mode: {mode}. Must be an instance of AgentMode.")

        self.mode = mode
        if activity is not None:
            self.activity = activity
        if error is not None:
            self.error = error
        elif mode in (AgentMode.IDLE, AgentMode.PLANNING, AgentMode.EXECUTING, AgentMode.COMPLETED):
            # Clear error on successful transitions unless explicitly provided
            self.error = None

        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))
        if confidence is not None:
            self.confidence = max(0.0, min(1.0, float(confidence)))
        if active_app is not None:
            self.active_app = active_app
        if permission_level is not None:
            self.permission_level = int(permission_level)
        else:
            # Track the mode's ceiling by default, so a consumer can ask
            # "how destructive is this agent right now?" without hardcoding the
            # mode->tier mapping at every call site. An explicit value still wins.
            self.permission_level = MODE_PERMISSION[mode]

        self.updated_at = time.time()
        return self

    def can_perform(self, level: int) -> bool:
        """True if the active permission level covers `level`."""
        return self.permission_level >= int(level)

    def to_dict(self) -> Dict[str, Any]:
        """Returns a clean JSON-serializable dictionary representation."""
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

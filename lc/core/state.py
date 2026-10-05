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

        self.updated_at = time.time()
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Returns a clean JSON-serializable dictionary representation."""
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

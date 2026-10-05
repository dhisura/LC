"""Task-scoped ExecutionContext and cooperative Cancellation for LC."""

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Dict, Optional
import uuid

from lc.core.events import Event, EventBus, EventType
from lc.core.state import AgentMode, AgentState


class OperationCancelledError(Exception):
    """Raised when a task or workflow operation is cancelled cooperatively."""
    pass


class CancellationToken:
    """Thread-safe cooperative cancellation token."""

    def __init__(self):
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Signal that cancellation is requested."""
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        with self._lock:
            return self._is_cancelled

    def throw_if_cancelled(self) -> None:
        """Raise OperationCancelledError if cancellation was requested."""
        if self.is_cancelled():
            raise OperationCancelledError("Task execution was cancelled by user request.")


@dataclass
class ExecutionContext:
    """Carries task-scoped execution state, signals, and bus references without globals."""
    task_id: str
    session_id: str
    workspace: Path
    state: AgentState
    event_bus: EventBus
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task: str,
        workspace: str = ".",
        session_id: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        state: Optional[AgentState] = None,
    ) -> "ExecutionContext":
        """Factory creating a new initialized ExecutionContext."""
        tid = f"task_{uuid.uuid4().hex[:8]}"
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        ws = Path(workspace).resolve()
        bus = event_bus or EventBus()
        st = state or AgentState(task=task)
        st.task = task

        return cls(
            task_id=tid,
            session_id=sid,
            workspace=ws,
            state=st,
            event_bus=bus,
        )

    def emit(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """Convenience method to emit an event associated with this context."""
        event = Event(
            event_type=event_type,
            session_id=self.session_id,
            task_id=self.task_id,
            payload=payload or {}
        )
        self.event_bus.publish(event)

    def transition_state(
        self,
        mode: AgentMode,
        activity: Optional[str] = None,
        error: Optional[str] = None,
        progress: Optional[float] = None,
        confidence: Optional[float] = None,
        permission_level: Optional[int] = None,
    ) -> AgentState:
        """Transitions state and automatically publishes a state change event."""
        prev_mode = self.state.mode
        self.state.transition(
            mode=mode,
            activity=activity,
            error=error,
            progress=progress,
            confidence=confidence,
            permission_level=permission_level,
        )
        self.emit(EventType.STATE_CHANGED, {
            "previous_mode": prev_mode.value,
            "new_mode": self.state.mode.value,
            "activity": self.state.activity,
            "progress": self.state.progress,
            "confidence": self.state.confidence,
            "error": self.state.error,
        })
        return self.state

    def check_cancelled(self) -> None:
        """Checks cancellation token and aborts if signaled."""
        self.cancellation_token.throw_if_cancelled()

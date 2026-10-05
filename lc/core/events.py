"""Synchronous internal EventBus and typed Event contracts for LC."""

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable, Dict, List, Set


class EventType:
    """Standardized event topic contracts for the agent runtime."""
    TASK_STARTED = "agent.task.started"
    TASK_COMPLETED = "agent.task.completed"
    TASK_FAILED = "agent.task.failed"
    TASK_CANCELLED = "agent.task.cancelled"

    PLAN_CREATED = "agent.plan.created"

    TOOL_REQUESTED = "agent.tool.requested"
    TOOL_APPROVED = "agent.tool.approved"
    TOOL_DENIED = "agent.tool.denied"
    TOOL_STARTED = "agent.tool.started"
    TOOL_COMPLETED = "agent.tool.completed"
    TOOL_FAILED = "agent.tool.failed"

    PERMISSION_REQUIRED = "agent.permission.required"

    VERIFICATION_STARTED = "agent.verification.started"
    VERIFICATION_PASSED = "agent.verification.passed"
    VERIFICATION_FAILED = "agent.verification.failed"

    STATE_CHANGED = "agent.state.changed"


@dataclass(frozen=True)
class Event:
    """Immutable event payload published across the agent runtime."""
    event_type: str
    session_id: str = ""
    task_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[Event], None]


class EventBus:
    """Thread-safe, synchronous pub/sub event bus."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type, or '*' for all events."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Unregister a handler. Returns True if removed, False otherwise."""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    if not self._subscribers[event_type]:
                        del self._subscribers[event_type]
                    return True
                except ValueError:
                    return False
            return False

    def publish(self, event: Event) -> None:
        """Synchronously dispatch an event to all registered subscribers."""
        handlers_to_call: List[EventHandler] = []

        with self._lock:
            # Type-specific subscribers
            if event.event_type in self._subscribers:
                handlers_to_call.extend(self._subscribers[event.event_type])
            # Wildcard subscribers
            if "*" in self._subscribers:
                handlers_to_call.extend(self._subscribers["*"])

        # Call handlers outside of the lock to prevent re-entrant deadlocks
        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception as e:
                # EventBus does not crash the publisher on subscriber error;
                # in future phases this will route to an audit logger.
                pass

    def clear(self) -> None:
        """Clear all registered event handlers."""
        with self._lock:
            self._subscribers.clear()

"""Agent Runtime orchestrator for state, events, and workflows in LC."""

from pathlib import Path
from typing import Any, Optional, Protocol, Union
import uuid

from lc.core.context import ExecutionContext, OperationCancelledError
from lc.core.events import EventBus, EventType
from lc.core.state import AgentMode, AgentState


class Workflow(Protocol):
    """Minimal protocol for executable workflows coordinated by the AgentRuntime."""
    def run(self, context: ExecutionContext) -> Any:
        ...


class AgentRuntime:
    """Core Agent Runtime managing authoritative state, event bus, and workflow lifecycles.
    
    This runtime does NOT contain workflow domain logic (PM/DEV/QA/QC), LLM prompts,
    or direct system execution. It acts strictly as the nervous system coordination layer.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        state: Optional[AgentState] = None,
    ):
        self.event_bus = event_bus or EventBus()
        self.state = state or AgentState()
        self._current_context: Optional[ExecutionContext] = None

    def create_context(
        self,
        task: str,
        workspace: Union[str, Path] = ".",
        session_id: Optional[str] = None,
    ) -> ExecutionContext:
        """Create a new task-scoped execution context bound to this runtime."""
        self.state.task = task
        self.state.transition(AgentMode.IDLE, activity="context_created")
        
        ctx = ExecutionContext.create(
            task=task,
            workspace=str(workspace),
            session_id=session_id,
            event_bus=self.event_bus,
            state=self.state,
        )
        self._current_context = ctx
        return ctx

    def execute_workflow(self, workflow: Workflow, context: ExecutionContext) -> Any:
        """Executes a workflow within the managed lifecycle, publishing standard events."""
        self._current_context = context

        # 1. Start Task
        context.transition_state(AgentMode.PLANNING, activity="task_started")
        context.emit(EventType.TASK_STARTED, {
            "task": context.state.task,
            "workspace": str(context.workspace),
        })

        try:
            # 2. Check early cancellation
            context.check_cancelled()

            # 3. Transition to executing
            context.transition_state(AgentMode.EXECUTING, activity="running_workflow")

            # 4. Run Workflow
            result = workflow.run(context)

            # 5. Check late cancellation
            context.check_cancelled()

            # 6. Complete Task
            context.transition_state(
                AgentMode.COMPLETED,
                activity="workflow_completed",
                progress=1.0,
            )
            context.emit(EventType.TASK_COMPLETED, {
                "task": context.state.task,
                "result": str(result) if result is not None else "",
            })
            return result

        except OperationCancelledError as oce:
            context.transition_state(
                AgentMode.CANCELLED,
                activity="task_cancelled",
                error=str(oce),
            )
            context.emit(EventType.TASK_CANCELLED, {
                "task": context.state.task,
                "reason": str(oce),
            })
            raise

        except Exception as e:
            context.transition_state(
                AgentMode.FAILED,
                activity="task_failed",
                error=str(e),
            )
            context.emit(EventType.TASK_FAILED, {
                "task": context.state.task,
                "error": str(e),
            })
            raise

    def cancel_active_task(self) -> bool:
        """Requests cancellation of the currently active context if present."""
        if self._current_context:
            self._current_context.cancellation_token.cancel()
            return True
        return False

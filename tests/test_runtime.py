"""Unit tests for Phase 1 Core Agent Runtime, State, EventBus, and Context."""

import unittest
from pathlib import Path
from lc.core.state import AgentMode, AgentState
from lc.core.events import Event, EventBus, EventType
from lc.core.context import ExecutionContext, CancellationToken, OperationCancelledError
from lc.core.runtime import AgentRuntime, Workflow


class TestAgentState(unittest.TestCase):
    def test_default_state(self):
        state = AgentState()
        self.assertEqual(state.task, "")
        self.assertEqual(state.mode, AgentMode.IDLE)
        self.assertEqual(state.activity, "")
        self.assertIsNone(state.active_app)
        self.assertEqual(state.permission_level, 0)
        self.assertEqual(state.progress, 0.0)
        self.assertEqual(state.confidence, 1.0)
        self.assertIsNone(state.error)

    def test_state_transitions(self):
        state = AgentState(task="Build API")
        state.transition(
            mode=AgentMode.PLANNING,
            activity="analyzing_specs",
            progress=0.1,
            confidence=0.85,
        )
        self.assertEqual(state.mode, AgentMode.PLANNING)
        self.assertEqual(state.activity, "analyzing_specs")
        self.assertEqual(state.progress, 0.1)
        self.assertEqual(state.confidence, 0.85)

        # Transition with error
        state.transition(
            mode=AgentMode.FAILED,
            activity="compilation_error",
            error="SyntaxError: invalid syntax",
        )
        self.assertEqual(state.mode, AgentMode.FAILED)
        self.assertEqual(state.error, "SyntaxError: invalid syntax")

    def test_invalid_mode_raises(self):
        state = AgentState()
        with self.assertRaises(ValueError):
            state.transition("INVALID_STRING_MODE")  # type: ignore

    def test_serialization(self):
        state = AgentState(task="Refactor", mode=AgentMode.EXECUTING, progress=0.5)
        d = state.to_dict()
        self.assertEqual(d["task"], "Refactor")
        self.assertEqual(d["mode"], "executing")
        self.assertEqual(d["progress"], 0.5)


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_and_publish(self):
        received = []

        def handler(event: Event):
            received.append(event)

        self.bus.subscribe(EventType.TASK_STARTED, handler)
        self.bus.publish(Event(event_type=EventType.TASK_STARTED, payload={"task": "Run tests"}))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload["task"], "Run tests")

    def test_multiple_subscribers_and_wildcard(self):
        received_specific = []
        received_wildcard = []

        self.bus.subscribe(EventType.TOOL_STARTED, lambda e: received_specific.append(e))
        self.bus.subscribe("*", lambda e: received_wildcard.append(e))

        self.bus.publish(Event(event_type=EventType.TOOL_STARTED, payload={"tool": "read_file"}))
        self.bus.publish(Event(event_type=EventType.TASK_COMPLETED, payload={"status": "ok"}))

        self.assertEqual(len(received_specific), 1)
        self.assertEqual(len(received_wildcard), 2)

    def test_unsubscribe(self):
        received = []
        handler = lambda e: received.append(e)

        self.bus.subscribe(EventType.TASK_COMPLETED, handler)
        self.bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        self.assertEqual(len(received), 1)

        unsub_ok = self.bus.unsubscribe(EventType.TASK_COMPLETED, handler)
        self.assertTrue(unsub_ok)

        self.bus.publish(Event(event_type=EventType.TASK_COMPLETED))
        self.assertEqual(len(received), 1)


class TestExecutionContextAndCancellation(unittest.TestCase):
    def test_context_creation_and_emit(self):
        bus = EventBus()
        events = []
        bus.subscribe(EventType.STATE_CHANGED, lambda e: events.append(e))

        ctx = ExecutionContext.create(task="Test Task", event_bus=bus)
        self.assertTrue(ctx.task_id.startswith("task_"))
        self.assertTrue(ctx.session_id.startswith("sess_"))
        self.assertEqual(ctx.state.task, "Test Task")

        ctx.transition_state(AgentMode.EXECUTING, activity="running_worker")
        self.assertEqual(ctx.state.mode, AgentMode.EXECUTING)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["new_mode"], "executing")

    def test_cancellation_token(self):
        token = CancellationToken()
        self.assertFalse(token.is_cancelled())

        token.cancel()
        self.assertTrue(token.is_cancelled())

        with self.assertRaises(OperationCancelledError):
            token.throw_if_cancelled()


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.runtime = AgentRuntime(event_bus=self.bus)

    def test_workflow_lifecycle_success(self):
        events_emitted = []
        self.bus.subscribe("*", lambda e: events_emitted.append(e.event_type))

        class MockSuccessfulWorkflow:
            def run(self, context: ExecutionContext):
                return {"result": "success"}

        ctx = self.runtime.create_context("Sample Task")
        output = self.runtime.execute_workflow(MockSuccessfulWorkflow(), ctx)

        self.assertEqual(output, {"result": "success"})
        self.assertEqual(self.runtime.state.mode, AgentMode.COMPLETED)
        self.assertIn(EventType.TASK_STARTED, events_emitted)
        self.assertIn(EventType.TASK_COMPLETED, events_emitted)

    def test_workflow_lifecycle_failure(self):
        events_emitted = []
        self.bus.subscribe("*", lambda e: events_emitted.append(e.event_type))

        class MockFailingWorkflow:
            def run(self, context: ExecutionContext):
                raise RuntimeError("Critical workflow failure")

        ctx = self.runtime.create_context("Failing Task")
        with self.assertRaises(RuntimeError):
            self.runtime.execute_workflow(MockFailingWorkflow(), ctx)

        self.assertEqual(self.runtime.state.mode, AgentMode.FAILED)
        self.assertEqual(self.runtime.state.error, "Critical workflow failure")
        self.assertIn(EventType.TASK_FAILED, events_emitted)

    def test_workflow_cancellation(self):
        events_emitted = []
        self.bus.subscribe("*", lambda e: events_emitted.append(e.event_type))

        class MockCancelledWorkflow:
            def run(self, context: ExecutionContext):
                context.cancellation_token.cancel()
                context.check_cancelled()

        ctx = self.runtime.create_context("Cancellable Task")
        with self.assertRaises(OperationCancelledError):
            self.runtime.execute_workflow(MockCancelledWorkflow(), ctx)

        self.assertEqual(self.runtime.state.mode, AgentMode.CANCELLED)
        self.assertIn(EventType.TASK_CANCELLED, events_emitted)


if __name__ == "__main__":
    unittest.main()

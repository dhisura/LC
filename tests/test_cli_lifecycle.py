"""Tests for the sprint lifecycle wiring in the CLI.

`run_sprint` now delegates to `AgentRuntime.execute_workflow` instead of
emitting lifecycle events by hand. These assert the properties that refactor
was supposed to buy: exactly one event per lifecycle moment, and a planning
gate that abort produces a real CANCELLED state rather than a silent return.
"""
import unittest
from unittest import mock

from lc.cli import LCSprintOrchestrator, SprintRejected
from lc.core.events import EventType
from lc.core.state import AgentMode


class FakeTicket:
    title = "Fake Ticket"
    task = "do a thing"
    stack = "python"
    missing_items: list = []
    acceptance_criteria = ["works"]
    definition_of_done = "done"
    suggested_files = ["calc.py"]


class FakeQAResult:
    def __init__(self, success):
        self.success = success
        self.command = "pytest"
        self.output = "output"
        self.exit_code = 0 if success else 1
        self.attempt = 1
        self.error_summary = "" if success else "boom"


def build_orchestrator(tmp, *, approved=True, qa_success=True, qc_approved=True):
    """An orchestrator with every LLM-backed role stubbed out."""
    with mock.patch("lc.cli.LCSprintOrchestrator.__init__", return_value=None):
        orch = LCSprintOrchestrator()

    from lc.core.runtime import AgentRuntime
    from lc.tools.guard import ExecutionGuard
    from lc.engine.memory import MemoryManager

    orch.workspace = str(tmp)
    orch.runtime = AgentRuntime()
    orch.guard = ExecutionGuard(auto_approve=approved)
    orch.memory = mock.MagicMock()
    orch.llm = mock.MagicMock()
    orch.llm.is_available.return_value = True
    orch.llm.model = "fake"
    orch.console = mock.MagicMock()
    orch.skill_manager = mock.MagicMock()
    orch.skill_manager.skills = {}
    orch.skill_manager.get_prompt_context.return_value = ""

    orch.pm = mock.MagicMock()
    orch.pm.plan_ticket.return_value = FakeTicket()
    orch.dev = mock.MagicMock()
    orch.dev.write_solution.return_value = [{"file": "calc.py", "diff_lines": 3}]
    orch.qa = mock.MagicMock()
    orch.qa.verify_solution.return_value = FakeQAResult(qa_success)
    orch.qc = mock.MagicMock()

    report = mock.MagicMock()
    report.approved = qc_approved
    report.feedback = "looks bloated"
    orch.qc.review_sprint.return_value = report

    orch.console.prompt_gate.return_value = approved
    return orch


class TestSprintLifecycle(unittest.TestCase):
    def setUp(self):
        # run_sprint prints user-facing status lines; keep them out of the
        # test report so a failure's output is readable.
        patcher = mock.patch("builtins.print")
        self.mock_print = patcher.start()
        self.addCleanup(patcher.stop)

    def _temp(self):
        import tempfile
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        from pathlib import Path
        return Path(holder.name)

    def test_successful_sprint_emits_one_task_started_and_completed(self):
        orch = build_orchestrator(self._temp())
        seen = []
        orch.runtime.event_bus.subscribe("*", lambda e: seen.append(e.event_type))

        self.assertTrue(orch.run_sprint("build it"))

        self.assertEqual(seen.count(EventType.TASK_STARTED), 1)
        self.assertEqual(seen.count(EventType.TASK_COMPLETED), 1)
        self.assertNotIn(EventType.TASK_FAILED, seen)
        self.assertEqual(orch.runtime.state.mode, AgentMode.COMPLETED)

    def test_aborting_the_planning_gate_cancels_through_the_runtime(self):
        orch = build_orchestrator(self._temp(), approved=False)
        seen = []
        orch.runtime.event_bus.subscribe("*", lambda e: seen.append(e.event_type))

        self.assertFalse(orch.run_sprint("build it"))

        # The old code returned False after emitting by hand; the gate now
        # cancels the token so the runtime owns the state transition.
        self.assertEqual(orch.runtime.state.mode, AgentMode.CANCELLED)
        self.assertIn(EventType.TASK_CANCELLED, seen)
        # The task did start (the runtime emits TASK_STARTED before running the
        # workflow); what must not happen is any work getting done.
        self.assertIn(EventType.TASK_STARTED, seen)
        orch.dev.write_solution.assert_not_called()

    def test_qc_rejection_becomes_a_task_failure(self):
        orch = build_orchestrator(self._temp(), qc_approved=False)
        seen = []
        orch.runtime.event_bus.subscribe("*", lambda e: seen.append(e.event_type))

        self.assertFalse(orch.run_sprint("build it"))

        self.assertEqual(orch.runtime.state.mode, AgentMode.FAILED)
        self.assertIn(EventType.TASK_FAILED, seen)
        self.assertIn("bloated", orch.runtime.state.error or "")

    def test_failing_qa_halts_before_qc(self):
        orch = build_orchestrator(self._temp(), qa_success=False)
        seen = []
        orch.runtime.event_bus.subscribe("*", lambda e: seen.append(e.event_type))

        self.assertFalse(orch.run_sprint("build it"))

        self.assertIn(EventType.TASK_FAILED, seen)
        orch.qc.review_sprint.assert_not_called()

    def test_cancellation_between_roles_stops_the_sprint(self):
        orch = build_orchestrator(self._temp())
        # Cancel as soon as DEV starts -- i.e. mid-sprint, from another thread
        # or a signal handler in the real app.
        def cancel_after_dev(ticket, **kwargs):
            orch.runtime.cancel_active_task()
            return [{"file": "calc.py", "diff_lines": 3}]

        orch.dev.write_solution.side_effect = cancel_after_dev

        self.assertFalse(orch.run_sprint("build it"))
        self.assertEqual(orch.runtime.state.mode, AgentMode.CANCELLED)
        # The QA loop must not have run after cancellation.
        orch.qa.verify_solution.assert_not_called()

    def test_cancel_with_no_active_task_returns_false(self):
        from lc.core.runtime import AgentRuntime
        self.assertFalse(AgentRuntime().cancel_active_task())


if __name__ == "__main__":
    unittest.main()
"""Command-Line Interface and Sprint Orchestrator for LC (LazyCorp)."""
import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from lc.config import DEFAULT_MODEL, OLLAMA_HOST, MAX_QA_RETRIES
from lc.core import AgentRuntime, AgentMode, EventType
from lc.core.context import ExecutionContext, OperationCancelledError
from lc.engine.llm import LLMClient
from lc.engine.memory import MemoryManager
from lc.engine.skills import SkillManager
from lc.tools.guard import ExecutionGuard
from lc.tools.system import SystemRunner
from lc.roles.pm import ProjectManager
from lc.roles.dev import Developer
from lc.roles.qa import QAEngineer, QAResult
from lc.roles.qc import QualityControl
from lc.ui.console import LCConsole


class SprintFailed(RuntimeError):
    """Raised when the sprint cannot deliver. Surfaces as a workflow failure.

    The runtime treats a returned value as success, so every unsuccessful exit
    from the sprint has to raise; returning False would publish TASK_COMPLETED.
    """


class SprintRejected(RuntimeError):
    """Raised when QC refuses to sign off. Surfaces as a workflow failure."""


class LCSprintOrchestrator:
    """Orchestrates the disciplined, lightweight multi-agent company sprint."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        workspace: str = ".",
        auto_approve: bool = False
    ):
        self.workspace = str(Path(workspace).resolve())
        self.runtime = AgentRuntime()
        self.console = LCConsole()
        self._attach_event_listeners(self.runtime.event_bus)
        self.guard = ExecutionGuard(auto_approve=auto_approve)
        self.runner = SystemRunner(guard=self.guard)
        self.memory = MemoryManager()
        self.llm = LLMClient(host=OLLAMA_HOST, model=model)
        self.skill_manager = SkillManager()
        self.skill_manager.discover()

        self.pm = ProjectManager(llm=self.llm, console=self.console, workspace=self.workspace)
        self.dev = Developer(llm=self.llm, console=self.console, workspace=self.workspace)
        self.qa = QAEngineer(llm=self.llm, runner=self.runner, console=self.console, workspace=self.workspace)
        self.qc = QualityControl(llm=self.llm, memory=self.memory, console=self.console, workspace=self.workspace)

    def _attach_event_listeners(self, event_bus) -> None:
        """Render lifecycle events as they happen.

        Nothing subscribed to the bus before, so every EVENT_* contract the
        runtime published went to no one -- the state machine was observable
        only by inspecting `runtime.state` after the fact.
        """
        def on_progress(event) -> None:
            progress = event.payload.get("progress")
            activity = event.payload.get("activity") or ""
            if progress is None or not activity:
                return
            print(f"\n  [{int(progress * 100):3d}%] {activity}")

        event_bus.subscribe(EventType.STATE_CHANGED, on_progress)

    def run_sprint(self, task: str) -> bool:
        """Executes the full company sprint lifecycle.

        The role sequence is wrapped in a Workflow and run through
        `AgentRuntime.execute_workflow`, so lifecycle events (TASK_STARTED /
        COMPLETED / FAILED / CANCELLED) and the failure-mode transitions are
        published in exactly one place instead of being re-emitted by hand at
        every exit path.
        """
        ctx = self.runtime.create_context(task=task, workspace=self.workspace)

        class SprintWorkflow:
            """Adapts `execute_sprint` to the runtime's Workflow protocol."""

            def run(self, context) -> bool:
                return self_outer.execute_sprint(task, context)

        self_outer = self
        try:
            return bool(self.runtime.execute_workflow(SprintWorkflow(), ctx))
        except OperationCancelledError:
            print("\n\033[33mSprint cancelled by user.\033[0m\n")
            return False
        except SprintRejected as rej:
            print(f"\n\033[1;33m[!] Sprint completed with QC reservations: {rej}\033[0m\n")
            return False
        except SprintFailed:
            # The runtime already printed the fail-fast escalation and recorded
            # the session; the non-zero exit code is the signal.
            return False

    def execute_sprint(self, task: str, ctx: ExecutionContext) -> bool:
        """The sprint itself, assuming the runtime already owns the lifecycle."""
        self.console.print_banner(model_name=self.llm.model, task=task)

        # 1. Healthcheck
        if not self.llm.is_available():
            self.console.print_role_message(
                "GUARD",
                f"Cannot connect to Ollama at {OLLAMA_HOST}.\n"
                "Please verify Ollama is running (`ollama serve` or check system tray).",
                subtitle="Connection Error"
            )
            return False

        # 2. PM Pre-Flight & Planning
        ctx.transition_state(AgentMode.PLANNING, activity="preflight_and_planning")
        ticket = self.pm.plan_ticket(task)
        ctx.emit(EventType.PLAN_CREATED, {"title": ticket.title, "stack": ticket.stack})

        # 3. Planning Gate (Interactive Approval)
        if not self.guard.auto_approve:
            ctx.transition_state(AgentMode.WAITING_PERMISSION, activity="planning_gate_approval")
            approved = self.console.prompt_gate("Approve ticket plan and begin autonomous sprint?")
            if not approved:
                # Cancel through the token so the runtime publishes TASK_CANCELLED
                # and transitions to CANCELLED, like every other exit path.
                ctx.cancellation_token.cancel()
                ctx.check_cancelled()

        # 4. Vaccine Retrieval & Dev Implementation
        ctx.transition_state(AgentMode.EXECUTING, activity="writing_solution", progress=0.3)
        vaccines = self.memory.get_relevant_vaccines(stack=ticket.stack, query=ticket.task)
        if vaccines:
            self.console.print_vaccine_injected(vaccines)

        skills_context = self.skill_manager.get_prompt_context(stack=ticket.stack, task=ticket.task)
        if self.skill_manager.skills:
            skill_names = ", ".join(self.skill_manager.skills.keys())
            self.console.print_role_message("PM", f"[SKILLS ACTIVE]: Loaded {len(self.skill_manager.skills)} skill(s): {skill_names}", subtitle="Skill Plugins")

        dev_files = self.dev.write_solution(ticket, vaccines=vaccines, skills_context=skills_context)

        # 5. QA Verification & Fail-Fast Loop
        past_failures = []
        attempt = 1
        max_attempts = MAX_QA_RETRIES + 1
        qa_result: Optional[QAResult] = None

        while attempt <= max_attempts:
            # Cooperative cancellation: each role call is an LLM round-trip that
            # can take minutes, so check between them.
            ctx.check_cancelled()
            ctx.transition_state(AgentMode.VERIFYING, activity=f"qa_verification_attempt_{attempt}", progress=0.6)
            ctx.emit(EventType.VERIFICATION_STARTED, {"attempt": attempt})
            qa_result = self.qa.verify_solution(ticket, dev_files, attempt=attempt)
            if qa_result.success:
                ctx.emit(EventType.VERIFICATION_PASSED, {"attempt": attempt})
                break

            ctx.emit(EventType.VERIFICATION_FAILED, {"attempt": attempt, "error": qa_result.error_summary})
            past_failures.append(qa_result)
            if attempt < max_attempts:
                ctx.transition_state(AgentMode.EXECUTING, activity=f"auto_remediation_attempt_{attempt}", progress=0.5)
                self.console.print_role_message(
                    "DEV",
                    f"Refactoring solution based on QA error report (Fix attempt {attempt}/{MAX_QA_RETRIES})...",
                    subtitle="Auto-Remediation"
                )
                dev_files = self.dev.write_solution(
                    ticket,
                    vaccines=vaccines,
                    error_context=qa_result.error_summary or qa_result.output,
                    skills_context=skills_context
                )
            attempt += 1

        if not qa_result or not qa_result.success:
            err_msg = qa_result.output[:300] if qa_result else "Verification failed"
            self.console.print_role_message(
                "QA",
                f"🛑 **Sprint Halted (Fail-Fast Rule Triggered)**\n\n"
                f"Automated verification failed after {MAX_QA_RETRIES} fix attempts.\n"
                f"**Exact Blocker**:\n```text\n{qa_result.output[:600] if qa_result else 'Unknown'}\n```\n"
                "The team has stopped to prevent infinite loops. Review the blocker above.",
                subtitle="Fail-Fast Escalation"
            )
            self.memory.record_session(task=task, status="FAILED", summary="Failed verification limit")
            # Raise rather than return False: the runtime reads a returned value
            # as a *successful* workflow, so returning here published
            # TASK_COMPLETED for a sprint that failed verification.
            raise SprintFailed(f"Verification failed after {MAX_QA_RETRIES} fix attempts: {err_msg}")

        # 6. QC Sign-Off & Mistake Vaccine Creation
        ctx.transition_state(AgentMode.VERIFYING, activity="qc_final_review", progress=0.85)
        qc_report = self.qc.review_sprint(
            ticket=ticket,
            dev_files=dev_files,
            qa_result=qa_result,
            past_failures=past_failures
        )

        status_str = "SUCCESS" if qc_report.approved else "REJECTED"
        self.memory.record_session(task=task, status=status_str, summary=qc_report.feedback[:300])

        if qc_report.approved:
            ctx.transition_state(AgentMode.VERIFYING, activity="sprint_completed", progress=1.0)
            print("\n\033[1;32m[DONE] Sprint completed successfully! Everyone goes home on time.\033[0m\n")
            return True
        else:
            # Report a QC rejection as a workflow failure so the runtime sets
            # FAILED and publishes TASK_FAILED with the feedback attached.
            raise SprintRejected(qc_report.feedback or "QC rejected the sprint")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="lc",
        description="LC (LazyCorp) - Ultra-lightweight local-first multi-agent company."
    )
    parser.add_argument("task", nargs="?", help="Task description or prompt to execute")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--workspace", "-w", default=".", help="Workspace path to operate in")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve all gates and commands (non-interactive)")
    parser.add_argument("--vaccines", action="store_true", help="List all stored Mistake Vaccines")
    parser.add_argument("--models", action="store_true", help="Check connection and list local Ollama models")
    parser.add_argument("--skills", action="store_true", help="List all installed skill plugins")
    parser.add_argument("--new-skill", metavar="NAME", help="Scaffold a new skill plugin template in ~/.lc/skills/<name>")

    args = parser.parse_args()

    # Subcommand: list skills
    if args.skills:
        sm = SkillManager()
        skills = sm.discover()
        if not skills:
            print(f"No skills installed yet. Skills directory: {sm.skills_dir}")
            print("Create your first skill using: lc --new-skill <name>")
        else:
            print(f"\n[Installed Skills in {sm.skills_dir}]:")
            for s in skills:
                runner_status = "[Executable]" if s.run else "[Prompt-Only]"
                first_line = s.description.splitlines()[0] if s.description else "No description"
                print(f"  * {s.name} {runner_status}")
                print(f"    Summary: {first_line}")
                print(f"    Path: {s.path}\n")
        return

    # Subcommand: scaffold new skill
    if args.new_skill:
        path = SkillManager.create_skill_template(args.new_skill)
        print(f"\n[OK] Created skill template at: {path}")
        print("  - SKILL.md  (Edit this to give the AI instructions, rules, or documentation)")
        print("  - skill.py  (Optional: implement def run(context) -> dict for custom python code)\n")
        return

    # Subcommand: list vaccines
    if args.vaccines:
        mem = MemoryManager()
        vacs = mem.list_vaccines()
        console = LCConsole()
        if not vacs:
            print("No Mistake Vaccines logged yet. The database is clean!")
        else:
            console.print_vaccine_injected(vacs)
        return

    # Subcommand: list models
    if args.models:
        llm = LLMClient(host=OLLAMA_HOST, model=args.model)
        if not llm.is_available():
            print(f"Error: Ollama not reachable at {OLLAMA_HOST}")
            sys.exit(1)
        models = llm.list_models()
        print(f"Connected to Ollama at {OLLAMA_HOST}")
        print("Available models:")
        for m in models:
            active_marker = " (Active)" if m == args.model else ""
            print(f"  • {m}{active_marker}")
        return

    # Task input
    task = args.task
    if not task:
        print("\033[1;36m🏢 Welcome to LC (LazyCorp) Multi-Agent Company\033[0m")
        try:
            task = input("\nEnter project task or feature request: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

    if not task:
        print("No task provided. Exiting.")
        sys.exit(0)

    orchestrator = LCSprintOrchestrator(
        model=args.model,
        workspace=args.workspace,
        auto_approve=args.yes
    )
    success = orchestrator.run_sprint(task)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

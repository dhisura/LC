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


class LCSprintOrchestrator:
    """Orchestrates the disciplined, lightweight multi-agent company sprint."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        workspace: str = ".",
        auto_approve: bool = False
    ):
        self.workspace = str(Path(workspace).resolve())
        self.console = LCConsole()
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

    def run_sprint(self, task: str) -> bool:
        """Executes the full company sprint lifecycle."""
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
        ticket = self.pm.plan_ticket(task)

        # 3. Planning Gate (Interactive Approval)
        if not self.guard.auto_approve:
            approved = self.console.prompt_gate("Approve ticket plan and begin autonomous sprint?")
            if not approved:
                print("\n\033[33mSprint aborted by user at Planning Gate.\033[0m")
                return False

        # 4. Vaccine Retrieval & Dev Implementation
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
            qa_result = self.qa.verify_solution(ticket, dev_files, attempt=attempt)
            if qa_result.success:
                break

            past_failures.append(qa_result)
            if attempt < max_attempts:
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
            self.console.print_role_message(
                "QA",
                f"🛑 **Sprint Halted (Fail-Fast Rule Triggered)**\n\n"
                f"Automated verification failed after {MAX_QA_RETRIES} fix attempts.\n"
                f"**Exact Blocker**:\n```text\n{qa_result.output[:600] if qa_result else 'Unknown'}\n```\n"
                "The team has stopped to prevent infinite loops. Review the blocker above.",
                subtitle="Fail-Fast Escalation"
            )
            self.memory.record_session(task=task, status="FAILED", summary="Failed verification limit")
            return False

        # 6. QC Sign-Off & Mistake Vaccine Creation
        qc_report = self.qc.review_sprint(
            ticket=ticket,
            dev_files=dev_files,
            qa_result=qa_result,
            past_failures=past_failures
        )

        status_str = "SUCCESS" if qc_report.approved else "REJECTED"
        self.memory.record_session(task=task, status=status_str, summary=qc_report.feedback[:300])

        if qc_report.approved:
            print("\n\033[1;32m[DONE] Sprint completed successfully! Everyone goes home on time.\033[0m\n")
            return True
        else:
            print("\n\033[1;33m[!] Sprint completed with QC reservations.\033[0m\n")
            return False


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

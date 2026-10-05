"""Project Manager (PM / Tech Lead) Role.
Specialized in Pre-Flight Audits, Gap Analysis, and Ticket Specification.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from lc.roles.base import BaseRole
from lc.tools.files import FileManager
from lc.tools.system import SystemRunner


@dataclass
class Ticket:
    title: str
    task: str
    stack: str
    missing_items: List[str]
    acceptance_criteria: List[str]
    definition_of_done: str
    suggested_files: List[str]


class ProjectManager(BaseRole):
    """The organized, thorough PM who hates rework and flags missing details upfront."""

    def __init__(self, llm, console=None, workspace="."):
        system_prompt = (
            "You are the Lead Project Manager at LC (LazyCorp). You believe in discipline, clarity, "
            "and doing things right the first time to avoid overtime.\n"
            "Your job is to:\n"
            "1. Analyze the user's request against the current workspace.\n"
            "2. Identify WHAT IS MISSING: missing specs, dependencies, unhandled edge cases, or prerequisites.\n"
            "3. Create a tight, unambiguous ticket with Acceptance Criteria and Definition of Done.\n"
            "Keep the plan practical and minimal. Avoid feature creep or overengineering."
        )
        super().__init__(name="PM", title="Lead Project Manager", system_prompt=system_prompt, llm=llm, console=console)
        self.workspace = workspace
        self.file_manager = FileManager(workspace)
        self.runner = SystemRunner()

    def run_preflight_scan(self) -> Dict[str, Any]:
        """Scans workspace files and system environment for prerequisites."""
        files = self.file_manager.list_files(max_depth=2)
        
        # Detect tech stack
        stack = "python"
        for f in files:
            if f.endswith("package.json"):
                stack = "node"
                break
            elif f.endswith("Cargo.toml"):
                stack = "rust"
                break
            elif f.endswith("go.mod"):
                stack = "go"
                break

        # Check basic tool presence
        tool_checks = {}
        res = self.runner.run("python --version", role="PM", reason="Checking Python runtime")
        tool_checks["python"] = res.stdout if res.success else "Missing"

        res_git = self.runner.run("git --version", role="PM", reason="Checking Git presence")
        tool_checks["git"] = res_git.stdout if res_git.success else "Missing"

        return {
            "stack": stack,
            "existing_files": files[:20],
            "tool_checks": tool_checks
        }

    def plan_ticket(self, user_task: str) -> Ticket:
        """Audits requirements and generates a structured Ticket with missing items flagged."""
        scan = self.run_preflight_scan()
        
        prompt = f"""
User Task:
"{user_task}"

Workspace Environment:
- Detected Stack: {scan['stack']}
- Existing Files: {', '.join(scan['existing_files']) if scan['existing_files'] else '(Empty workspace)'}
- System Tools: {scan['tool_checks']}

Analyze this task and generate:
1. WHAT IS MISSING: List any missing prerequisites, ambiguous requirements, or dependencies.
2. ACCEPTANCE CRITERIA: 3-5 concrete testable criteria.
3. DEFINITION OF DONE: One sentence defining complete success.
4. PROPOSED FILES: Which 1-3 files should be created or updated (keep it minimal!).

Format your response clearly:
[MISSING]
- <item>

[CRITERIA]
- <criterion>

[DOD]
<definition of done>

[FILES]
- <filename>
"""
        raw_plan = self.generate(prompt, temperature=0.2)
        
        # Parse output into Ticket object
        missing_items = []
        criteria = []
        dod = "Tests pass and requirements met."
        suggested_files = []

        current_section = None
        for line in raw_plan.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if "[MISSING]" in line_str:
                current_section = "missing"
            elif "[CRITERIA]" in line_str:
                current_section = "criteria"
            elif "[DOD]" in line_str:
                current_section = "dod"
            elif "[FILES]" in line_str:
                current_section = "files"
            else:
                if current_section == "missing" and line_str.startswith("-"):
                    missing_items.append(line_str.lstrip("- ").strip())
                elif current_section == "criteria" and line_str.startswith("-"):
                    criteria.append(line_str.lstrip("- ").strip())
                elif current_section == "dod":
                    dod = line_str
                elif current_section == "files" and line_str.startswith("-"):
                    suggested_files.append(line_str.lstrip("- ").strip())

        if not criteria:
            criteria = ["Implements task cleanly", "Passes automated verification tests"]
        if not suggested_files:
            suggested_files = ["main.py" if scan["stack"] == "python" else "index.js"]

        ticket = Ticket(
            title=f"Sprint Ticket: {user_task[:50]}",
            task=user_task,
            stack=scan["stack"],
            missing_items=missing_items,
            acceptance_criteria=criteria,
            definition_of_done=dod,
            suggested_files=suggested_files
        )

        # Render PM Report
        report_text = f"**Task**: {ticket.task}\n\n"
        if ticket.missing_items:
            report_text += "**[!] What Was Missing / Addressed**:\n" + "\n".join(f"  * {m}" for m in ticket.missing_items) + "\n\n"
        else:
            report_text += "**[OK] Pre-Flight Check**: No blockers identified.\n\n"

        report_text += "**Acceptance Criteria**:\n" + "\n".join(f"  [ ] {c}" for c in ticket.acceptance_criteria) + "\n\n"
        report_text += f"**Definition of Done**: {ticket.definition_of_done}\n"
        report_text += f"**Proposed Files**: {', '.join(ticket.suggested_files)}"

        self.console.print_role_message("PM", report_text, subtitle="Sprint Plan & Pre-Flight Audit")
        return ticket

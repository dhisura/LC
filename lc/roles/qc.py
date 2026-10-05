"""Quality Control (QC / Principal Reviewer) Role.
Reviews diffs, enforces the Anti-Overtime Diff Budget, and generates Mistake Vaccines into SQLite.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from lc.roles.base import BaseRole
from lc.roles.pm import Ticket
from lc.roles.qa import QAResult
from lc.engine.memory import MemoryManager


@dataclass
class QCReport:
    approved: bool
    diff_score: str
    feedback: str
    vaccine_created: Optional[Dict[str, str]] = None


class QualityControl(BaseRole):
    """Principal Reviewer who rejects bloated overengineering and logs Mistake Vaccines."""

    def __init__(self, llm, memory=None, console=None, workspace="."):
        system_prompt = (
            "You are the Principal QC Engineer at LC (LazyCorp). You have the final say before code ships.\n"
            "Your priorities:\n"
            "1. Did the implementation fulfill the PM acceptance criteria?\n"
            "2. ANTI-OVERTIME DIFF BUDGET: Is the code clean, concise, and free from unnecessary bloat?\n"
            "   NOTE: Separate implementation and test files (e.g. calc.py and test_calc.py) are standard and expected.\n"
            "   Only reject if there are truly superfluous, unrequested files or massive boilerplate.\n"
            "3. If all tests pass and requirements are met cleanly, mark as APPROVED.\n"
            "Be fair, rigorous, and concise."
        )
        super().__init__(name="QC", title="Principal Quality Control", system_prompt=system_prompt, llm=llm, console=console)
        self.workspace = workspace
        self.memory = memory or MemoryManager()

    def review_sprint(
        self,
        ticket: Ticket,
        dev_files: List[Dict[str, Any]],
        qa_result: QAResult,
        past_failures: List[QAResult]
    ) -> QCReport:
        """Audits the sprint outcome, checks diff budget, and records vaccine if needed."""
        total_diff_lines = sum(d.get("diff_lines", 0) for d in dev_files)
        files_changed = [d["file"] for d in dev_files]

        prompt = f"""
Sprint Review:
Task: {ticket.task}
Files Modified: {', '.join(files_changed)}
Total Added Lines: {total_diff_lines}
QA Status: {'PASSED' if qa_result.success else 'FAILED'}

Acceptance Criteria:
{chr(10).join(f'- {c}' for c in ticket.acceptance_criteria)}

Audit the work:
1. Criteria Compliance: Are requirements satisfied?
2. Anti-Overtime Diff Budget: Is the code suitably concise (score: Excellent / Acceptable / Bloated)?
   (Separate source and test files are standard practice and expected).
3. Final Verdict: APPROVED (if tests pass and criteria met) or REJECTED (only if broken or severely bloated).

Format:
[VERDICT]
APPROVED (or REJECTED)

[DIFF_SCORE]
<Excellent / Acceptable / Bloated>

[FEEDBACK]
<concise evaluation>
"""
        raw_review = self.generate(prompt, temperature=0.1)

        approved = qa_result.success and "APPROVED" in raw_review.upper()
        diff_score = "Acceptable"
        feedback = raw_review

        for line in raw_review.splitlines():
            line_str = line.strip()
            if "[DIFF_SCORE]" in line_str:
                continue
            elif line_str in ("Excellent", "Acceptable", "Bloated"):
                diff_score = line_str

        # Generate Mistake Vaccine if an issue was encountered and fixed
        vaccine_data = None
        if past_failures and qa_result.success:
            first_fail = past_failures[0]
            vac_prompt = f"""
A bug occurred and was successfully fixed during the sprint:
Stack: {ticket.stack}
Task: {ticket.task}
Error Output:
{first_fail.output[:800]}

Generate a reusable Mistake Vaccine to prevent this in the future:
[SYMPTOM]
<1-sentence error description>

[ROOT_CAUSE]
<1-sentence cause>

[PREVENTION_RULE]
<Clear, direct imperative rule to avoid this in future code>
"""
            raw_vac = self.generate(vac_prompt, temperature=0.1)
            symptom = "Runtime error during execution"
            root_cause = "Code syntax or path issue"
            rule = "Verify imports, file paths, and syntax before execution"

            # Parse vaccine sections cleanly
            for part in raw_vac.split("["):
                if part.startswith("SYMPTOM]"):
                    lines = [ln.strip() for ln in part.replace("SYMPTOM]", "").strip().splitlines() if ln.strip()]
                    if lines:
                        symptom = lines[0]
                elif part.startswith("ROOT_CAUSE]"):
                    lines = [ln.strip() for ln in part.replace("ROOT_CAUSE]", "").strip().splitlines() if ln.strip()]
                    if lines:
                        root_cause = lines[0]
                elif part.startswith("PREVENTION_RULE]"):
                    lines = [ln.strip() for ln in part.replace("PREVENTION_RULE]", "").strip().splitlines() if ln.strip()]
                    if lines:
                        rule = lines[0]

            vaccine_id = self.memory.record_vaccine(
                stack=ticket.stack,
                symptom=symptom,
                root_cause=root_cause,
                prevention_rule=rule
            )
            vaccine_data = {
                "id": str(vaccine_id),
                "stack": ticket.stack,
                "symptom": symptom,
                "prevention_rule": rule
            }

            self.console.print_role_message(
                "QC",
                f"[VACCINE] **Mistake Vaccine Created & Logged to SQLite (ID: #{vaccine_id})**\n\n"
                f"**Symptom**: {symptom}\n"
                f"**Rule**: `{rule}`\n\n"
                "The team is now permanently immunized against this bug across all future tasks.",
                subtitle="Institutional Memory Updated"
            )

        report = QCReport(
            approved=approved,
            diff_score=diff_score,
            feedback=feedback,
            vaccine_created=vaccine_data
        )

        status_icon = "[OK] APPROVED" if approved else "[REJECTED]"
        msg = f"**Final Audit Status**: {status_icon}\n" \
              f"**Anti-Overtime Diff Rating**: {diff_score} ({total_diff_lines} lines changed across {len(files_changed)} files)\n\n" \
              f"{feedback[:400]}"
        self.console.print_role_message("QC", msg, subtitle="Final Sign-Off")

        return report

"""Senior Minimalist Developer Role.
Enforces the Anti-Overtime Diff Budget and injects Mistake Vaccines.
"""
from typing import List, Dict, Any, Optional
from lc.roles.base import BaseRole
from lc.roles.pm import Ticket
from lc.tools.files import FileManager


class Developer(BaseRole):
    """Senior Minimalist Developer who writes clean, robust code on the first try."""

    def __init__(self, llm, console=None, workspace="."):
        system_prompt = (
            "You are the Senior Minimalist Developer at LC (LazyCorp). You are a high performer who refuses to "
            "waste time on overengineering, excessive boilerplate, or unnecessary files because you want to go home on time.\n"
            "Your philosophy:\n"
            "- Write the simplest, cleanest solution that satisfies the acceptance criteria.\n"
            "- Never create 5 files when 1 or 2 files do the job perfectly.\n"
            "- Do not add speculative features or unused abstractions.\n"
            "- For Python tests, always use the standard library 'unittest' (import unittest) to avoid uninstalled dependencies like pytest.\n"
            "- Adhere strictly to past Mistake Vaccines provided to avoid rework.\n"
            "- Always write code that can be easily tested."
        )
        super().__init__(name="DEV", title="Senior Minimalist Dev", system_prompt=system_prompt, llm=llm, console=console)
        self.workspace = workspace
        self.file_manager = FileManager(workspace)

    def write_solution(
        self,
        ticket: Ticket,
        vaccines: List[Dict[str, Any]],
        error_context: str = "",
        skills_context: str = ""
    ) -> List[Dict[str, Any]]:
        """Generates minimal code, writes files, and returns diff results."""
        vaccine_context = ""
        if vaccines:
            vaccine_lines = [f"- {v.get('stack')}: {v.get('prevention_rule')}" for v in vaccines]
            vaccine_context = "### [VACCINE] MISTAKE VACCINES (MANDATORY RULES FROM PAST BUGS):\n" + "\n".join(vaccine_lines)

        retry_context = ""
        if error_context:
            retry_context = f"\n### [!] PREVIOUS ATTEMPT FAILED QA:\n{error_context}\nFix the exact root cause directly with minimal changes."

        skills_block = f"\n{skills_context}" if skills_context else ""

        prompt = f"""
### TICKET SPECIFICATION:
Title: {ticket.title}
Task: {ticket.task}
Target Files: {', '.join(ticket.suggested_files)}

Acceptance Criteria:
{chr(10).join(f'- {c}' for c in ticket.acceptance_criteria)}

Definition of Done:
{ticket.definition_of_done}

{vaccine_context}
{skills_block}
{retry_context}

INSTRUCTIONS:
Output the complete, working code for each target file.
Format every file clearly like this:
[FILE: relative/path/to/file.ext]
```language
...code...
```
[END FILE]
"""
        raw_output = self.generate(prompt, temperature=0.1)

        # Parse and write files
        results = []
        lines = raw_output.splitlines()
        current_file = None
        code_lines = []
        in_block = False

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("[FILE:") and "]" in line_str:
                current_file = line_str.split("[FILE:")[1].split("]")[0].strip().strip("`'\"")
                code_lines = []
                in_block = False
            elif line_str == "[END FILE]":
                if current_file and code_lines:
                    full_code = "\n".join(code_lines).strip() + "\n"
                    bytes_written, diff = self.file_manager.write_file(current_file, full_code)
                    diff_lines = self.file_manager.count_diff_lines(diff)
                    results.append({
                        "file": current_file,
                        "bytes": bytes_written,
                        "diff": diff,
                        "diff_lines": diff_lines
                    })
                    self.console.print_diff(diff, filename=current_file)
                current_file = None
                code_lines = []
            elif current_file is not None:
                if line_str.startswith("```"):
                    in_block = not in_block
                    continue
                code_lines.append(line)

        # Fallback if no delimiter was matched properly
        if not results and ticket.suggested_files:
            fallback_file = ticket.suggested_files[0]
            clean_code = raw_output
            if "```" in clean_code:
                parts = clean_code.split("```")
                if len(parts) >= 3:
                    clean_code = parts[1]
                    if "\n" in clean_code:
                        clean_code = clean_code.split("\n", 1)[1]
            bytes_written, diff = self.file_manager.write_file(fallback_file, clean_code)
            results.append({
                "file": fallback_file,
                "bytes": bytes_written,
                "diff": diff,
                "diff_lines": self.file_manager.count_diff_lines(diff)
            })
            self.console.print_diff(diff, filename=fallback_file)

        summary_msg = f"Completed implementation with minimal footprint:\n" + \
                      "\n".join(f"  • `{r['file']}` ({r['diff_lines']} added lines)" for r in results)
        self.console.print_role_message("DEV", summary_msg, subtitle="Anti-Overtime Implementation")
        return results

"""Rich terminal UI and role status rendering with colorama fallback."""
import sys
from typing import Optional, List, Dict, Any

# Ensure UTF-8 output on Windows consoles to prevent cp1252 UnicodeEncodeError
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.theme import Theme
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class LCConsole:
    """Renders formatted, color-coded role events to the terminal."""

    ROLE_THEMES = {
        "PM": {"color": "cyan", "icon": "[PM]", "title": "Project Manager"},
        "DEV": {"color": "green", "icon": "[DEV]", "title": "Senior Minimalist Dev"},
        "QA": {"color": "yellow", "icon": "[QA]", "title": "Verification QA"},
        "QC": {"color": "magenta", "icon": "[QC]", "title": "Quality Control"},
        "GUARD": {"color": "red", "icon": "[GUARD]", "title": "Execution Guard"},
        "VACCINE": {"color": "bright_blue", "icon": "[VACCINE]", "title": "Mistake Vaccine"}
    }

    def __init__(self):
        if RICH_AVAILABLE:
            custom_theme = Theme({
                "pm": "bold cyan",
                "dev": "bold green",
                "qa": "bold yellow",
                "qc": "bold magenta",
                "guard": "bold red",
                "vaccine": "bold blue"
            })
            self.console = Console(theme=custom_theme, legacy_windows=False)
        else:
            self.console = None

    def print_banner(self, model_name: str, task: str):
        """Displays startup company banner."""
        if RICH_AVAILABLE:
            banner_text = f"[bold white]LC (LazyCorp) Multi-Agent Company[/bold white]\n" \
                          f"[dim]Engine: Ollama ({model_name}) | Memory: SQLite | Guard: Active[/dim]\n\n" \
                          f"[bold yellow]Current Sprint:[/bold yellow] [italic]{task}[/italic]"
            self.console.print(Panel(banner_text, border_style="bold blue", expand=False))
        else:
            print("=" * 60)
            print(" LC (LazyCorp) Multi-Agent Company")
            print(f" Engine: Ollama ({model_name}) | Guard: Active")
            print(f" Sprint: {task}")
            print("=" * 60)

    def print_role_message(self, role: str, message: str, subtitle: str = ""):
        """Prints a role message in a dedicated color panel."""
        cfg = self.ROLE_THEMES.get(role.upper(), {"color": "white", "icon": "🤖", "title": role})
        if RICH_AVAILABLE:
            panel = Panel(
                message.strip(),
                title=f"{cfg['icon']} [bold {cfg['color']}]{cfg['title']}[/bold {cfg['color']}]",
                subtitle=f"[dim]{subtitle}[/dim]" if subtitle else None,
                border_style=cfg["color"],
                expand=True
            )
            self.console.print(panel)
        else:
            print(f"\n{cfg['icon']} [{cfg['title']}] {subtitle}")
            print("-" * 50)
            print(message.strip())
            print("-" * 50)

    def print_diff(self, diff_text: str, filename: str = ""):
        """Prints a unified diff cleanly."""
        if not diff_text.strip():
            return
        if RICH_AVAILABLE:
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
            self.console.print(Panel(syntax, title=f"📄 Diff: {filename}", border_style="dim green"))
        else:
            print(f"\n--- Diff: {filename} ---")
            print(diff_text)

    def print_vaccine_injected(self, vaccines: List[Dict[str, Any]]):
        """Prints applied mistake vaccines."""
        if not vaccines:
            return
        if RICH_AVAILABLE:
            table = Table(title="💉 Immunization: Past Mistake Vaccines Applied", border_style="blue")
            table.add_column("Stack", style="cyan", width=12)
            table.add_column("Symptom", style="yellow")
            table.add_column("Prevention Directive", style="green")
            for v in vaccines:
                table.add_row(v.get("stack", ""), v.get("symptom", ""), v.get("prevention_rule", ""))
            self.console.print(table)
        else:
            print("\n💉 [VACCINES APPLIED]")
            for v in vaccines:
                print(f"  • [{v.get('stack')}] {v.get('prevention_rule')}")

    def prompt_gate(self, prompt_text: str = "Approve plan and begin autonomous sprint?") -> bool:
        """Planning gate approval prompt."""
        if RICH_AVAILABLE:
            self.console.print(f"\n[bold green]👉 Planning Gate:[/bold green] {prompt_text}")
        else:
            print(f"\n👉 Planning Gate: {prompt_text}")
        
        try:
            choice = input("   [Y] Approve & Sprint | [N] Reject / Edit: ").strip().lower()
            return choice in ("y", "")
        except (KeyboardInterrupt, EOFError):
            return False

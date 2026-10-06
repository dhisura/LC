"""Configuration for LC, loaded from the environment with sensible defaults."""
import os
from pathlib import Path

def _augment_path() -> None:
    """Make locally-installed git/gh visible to the SystemRunner.

    Windows PowerShell does not inherit a PATH that was updated after the shell
    started, and git installs per-user under AppData. Uses os.pathsep rather than
    a hardcoded ';' so this is a no-op-safe helper on any platform.
    """
    candidates = [
        Path.home() / "AppData/Local/Programs/Git/cmd",
        Path.home() / "AppData/Local/Programs/Git/bin",
        Path("C:/Program Files/Git/cmd"),
        Path("C:/Program Files/GitHub CLI"),
        Path.home() / "AppData/Local/gh/bin",
    ]
    current = os.environ.get("PATH", "")
    for candidate in candidates:
        if candidate.exists() and str(candidate) not in current:
            current = f"{candidate}{os.pathsep}{current}"
    os.environ["PATH"] = current


# Engine configuration
OLLAMA_HOST = os.environ.get("LC_OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("LC_MODEL", "qwen2.5:3b")

# Institutional memory + skill plugins. Both live under ~/.lc, never in the
# source tree -- the repo is a checkout, this is machine state.
LC_HOME = Path(os.environ.get("LC_HOME", Path.home() / ".lc"))
DB_PATH = LC_HOME / "lc_memory.db"
SKILLS_DIR = LC_HOME / "skills"

# Execution limits
MAX_QA_RETRIES = 2
COMMAND_TIMEOUT = 120  # seconds

# Read-only commands the guard may auto-approve. Kept as documentation of the
# policy surface; lc.tools.guard holds the authoritative per-command rules.
SAFE_COMMAND_PREFIXES = (
    "dir", "ls", "get-childitem", "gci",
    "cat", "type", "get-content", "gc",
    "git status", "git diff", "git log", "git branch",
    "python --version", "node --version", "git --version",
    "where", "which", "get-command",
    "echo", "pwd", "get-location"
)


def _env_list(name: str):
    """Read a comma-separated environment variable into a tuple."""
    raw = os.environ.get(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


# Per-project additions to the ExecutionGuard's allowlists, so a project can
# auto-approve its own read-only tools without editing the guard or running
# with --yes.
#
#     setx LC_GUARD_EXTRA_SAFE_COMMANDS "npm, npx, bun"
#
# These can only *widen* the allowlist. Two things stay fixed regardless:
# the shell-metacharacter check (so `npm run x; rm -rf .` still needs
# approval) and the read-only-only nature of git subcommands (so `commit` and
# `push` cannot be added here).
GUARD_EXTRA_SAFE_COMMANDS = _env_list("LC_GUARD_EXTRA_SAFE_COMMANDS")
GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS = _env_list("LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS")
# Extra path fragments treated as credential material, e.g. a project-specific
# secrets directory.
GUARD_EXTRA_SENSITIVE_MARKERS = _env_list("LC_GUARD_EXTRA_SENSITIVE_MARKERS")

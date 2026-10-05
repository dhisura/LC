import os
from pathlib import Path

# Auto-include local Git and gh paths if present
GIT_PATHS = [
    Path.home() / "AppData/Local/Programs/Git/cmd",
    Path.home() / "AppData/Local/Programs/Git/bin",
    Path("C:/Program Files/Git/cmd"),
    Path.home() / "AppData/Local/gh/bin",
]
for gp in GIT_PATHS:
    if gp.exists() and str(gp) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{gp};{os.environ.get('PATH', '')}"

# Engine configuration
OLLAMA_HOST = os.environ.get("LC_OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("LC_MODEL", "qwen2.5:3b")

# Institutional Memory Database
LC_HOME = Path(os.environ.get("LC_HOME", Path.home() / ".lc"))
LC_HOME.mkdir(parents=True, exist_ok=True)
DB_PATH = LC_HOME / "lc_memory.db"

# Execution limits
MAX_QA_RETRIES = 2
COMMAND_TIMEOUT = 120  # seconds

# Safe commands that can run without interactive confirmation
SAFE_COMMAND_PREFIXES = (
    "dir", "ls", "get-childitem", "gci",
    "cat", "type", "get-content", "gc",
    "git status", "git diff", "git log", "git branch",
    "python --version", "node --version", "git --version",
    "where", "which", "get-command",
    "echo", "pwd", "get-location"
)

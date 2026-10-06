"""Execution Guard & Permission Interceptor for Windows system actions."""
from typing import FrozenSet, List, Optional, Tuple

# Characters that let one "command" do more than one thing, reach outside its
# argv, or write to disk. A command is only considered read-only if every one of
# these appears exclusively inside quotes.
#
# `$` and `(` matter because PowerShell expands subexpressions there: the whole
# of `echo $(Remove-Item -Recurse C:\)` looks like a bare `echo` otherwise.
_UNSAFE_CHARS = frozenset(";|&><`$()\n\r")

# Quote characters we understand, plus the PowerShell single-quote escape.
# Backtick escapes are handled positionally in _scan.
_QUOTES = frozenset("'\"")

# Read-only filesystem / environment cmdlets. Aliases included because the
# allowlist is matched against argv[0] exactly as the user typed it.
_READ_ONLY_COMMANDS: FrozenSet[str] = frozenset({
    "dir", "ls", "gci", "get-childitem",
    "cat", "type", "get-content", "gc",
    "echo", "write-output",
    "pwd", "get-location",
    "where", "which", "get-command",
    "select-string", "findstr",
    "measure-object", "test-path", "tree",
})

# Git plumbing that only reads. `commit`, `push`, `reset`, `checkout`, `clean`
# and friends are deliberately absent -- they all mutate the repo or remote.
_GIT_READ_ONLY_SUBCOMMANDS: FrozenSet[str] = frozenset({
    "status", "diff", "log", "show", "blame", "describe",
    "rev-parse", "ls-files", "ls-remote", "shortlog", "cat-file",
})

# Git subcommands that are read-only in intent but can also *do* things, so
# they need their flags checked individually.
_GIT_FLAG_ONLY_SUBCOMMANDS: FrozenSet[str] = frozenset({"branch", "remote"})

# Flags whose only purpose is to change how output is rendered/filtered.
_GIT_DISPLAY_FLAGS: FrozenSet[str] = frozenset({
    "-a", "--all", "-r", "--remotes", "-l", "--list", "-v", "--verbose",
    "-vv", "--show-current", "--contains", "--no-merged", "--merged",
    "--no-color", "--abbrev", "-n", "--name-only", "--name-status",
    "--oneline", "--graph", "--decorate", "-p", "--patch", "--stat",
    "--short", "--branch", "-u", "--untracked", "--tracked", "-q",
    "--quiet", "--color", "--no-patch", "--follow", "--reverse",
    "-i", "--ignore-case", "--sort", "--topo-order", "--date-order",
    "--author", "--committer", "--grep", "--since", "--until",
    "--after", "--before", "-n", "--skip", "--max-count",
})

# Git options that execute external programs or write to a file. `--ext-diff`
# and `--textconv` invoke drivers straight out of a gitconfig file, and
# `--output` / `-o` redirect the stream to disk.
_GIT_DENIED_ARGS: FrozenSet[str] = frozenset({
    "--output", "-o", "--exec", "--ext-diff", "--textconv", "--paginate",
    "--no-index", "--recurse-submodules",
})

# Interpreters may only be probed for their version. Letting `python` through
# with arbitrary arguments is `python -c "import os; ..."` by another name.
_VERSION_PROBES: FrozenSet[str] = frozenset({"--version", "-V", "-v", "--help", "-h"})
_INTERPRETERS: FrozenSet[str] = frozenset({"python", "python3", "py", "node"})

# Paths worth refusing to read even though the command reading them is safe.
# An autonomous agent that echoes these into an LLM prompt is exfiltrating.
_SENSITIVE_PATH_MARKERS: Tuple[str, ...] = (
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".ssh",
    ".aws", ".azure", ".kube", ".gnupg",
    "credentials", ".netrc", "shadow", ".env",
)


def _scan(text: str) -> Optional[List[str]]:
    """Split `text` into argv, or return None if it uses shell metacharacters.

    Quote-aware, so `git log --grep "a;b"` stays one argument while
    `echo hi; rm -rf C:\\` is rejected outright.
    """
    tokens: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    has_content = False

    i = 0
    while i < len(text):
        char = text[i]

        if quote == "'":
            # Inside single quotes only '' escapes; backslash is literal.
            if char == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    current.append("'")
                    i += 2
                    continue
                quote = None
            else:
                current.append(char)
            i += 1
            continue

        if quote == '"':
            if char == "`" and i + 1 < len(text):
                current.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                quote = None
            else:
                current.append(char)
            i += 1
            continue

        if char == "#" and not current:
            # Unquoted comment runs to end of line.
            while i < len(text) and text[i] not in "\n\r":
                i += 1
            continue

        if char in _QUOTES:
            quote = char
            has_content = True
            i += 1
            continue

        if char == "`":
            if i + 1 < len(text):
                current.append(text[i + 1])
                has_content = True
                i += 2
                continue
            return None

        if char in _UNSAFE_CHARS:
            return None

        if char.isspace():
            if current or has_content:
                tokens.append("".join(current))
                current = []
                has_content = False
            i += 1
            continue

        current.append(char)
        has_content = True
        i += 1

    if quote is not None:
        # Unbalanced quote -- refuse rather than guess at the intent.
        return None

    if current or has_content:
        tokens.append("".join(current))

    return tokens or None


class ExecutionGuard:
    """Guards execution by intercepting potentially modifying commands."""

    def __init__(self, auto_approve: bool = False):
        # One flag, two names -- `cli.py` reads `auto_approve`, and the
        # "always allow this session" answer below has to update both.
        self.auto_approve = auto_approve
        self.always_allow_session = auto_approve

    def is_safe_command(self, cmd: str) -> bool:
        """Check if command is purely read-only and safe to run silently.

        Every command is tokenized with quote awareness first: `git log; git push`
        and `echo x > file` are *not* safe commands that happen to start with a
        safe prefix, they are two commands / a write, and both are rejected.
        """
        argv = _scan(cmd)
        if argv is None:
            return False

        name = argv[0].lower()
        args = argv[1:]
        lowered = [a.lower() for a in args]

        # A bare version probe is safe for any tool, including the ones that are
        # otherwise never auto-approved (`git --version`, `pwsh --version`).
        if lowered and lowered[0] in ("--version", "-v") and len(argv) == 2:
            return True

        if name == "git":
            return self._is_allowed_git(args, lowered)

        if name in _READ_ONLY_COMMANDS:
            return self._is_allowed_args(lowered)

        if name in _INTERPRETERS:
            return bool(lowered) and all(a in _VERSION_PROBES for a in lowered)

        return False

    def _is_allowed_args(self, lowered: List[str]) -> bool:
        """Reject read-only commands pointed at credential material."""
        for arg in lowered:
            cleaned = arg.replace("\\", "/").replace("./", "")
            if any(marker in cleaned for marker in _SENSITIVE_PATH_MARKERS):
                return False
        return True

    def _is_allowed_git(self, args: List[str], lowered: List[str]) -> bool:
        if not lowered:
            return False

        # Skip global flags (and their values) to find the subcommand.
        index = 0
        while index < len(lowered):
            arg = lowered[index]
            if arg.startswith("-"):
                # `-C path`, `-c key=val`, ... take a value in the next token.
                if arg in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
                    index += 2
                    continue
                index += 1
                continue
            break

        if index >= len(lowered):
            return False

        subcommand = lowered[index]
        remaining = lowered[index + 1:]

        # `--output=file` smuggles the redirect past an exact-match check.
        if any(arg.split("=", 1)[0] in _GIT_DENIED_ARGS for arg in remaining):
            return False

        if subcommand in _GIT_READ_ONLY_SUBCOMMANDS:
            return self._is_allowed_args(lowered)

        if subcommand in _GIT_FLAG_ONLY_SUBCOMMANDS:
            # `git branch -d main` and `git remote add origin URL` mutate state;
            # only pure display flags keep these on the silent path.
            return all(arg.split("=", 1)[0] in _GIT_DISPLAY_FLAGS for arg in remaining)

        return False

    def request_approval(self, command: str, role: str = "Agent", reason: str = "") -> Tuple[bool, str]:
        """Intercept command and prompt user for approval if needed.

        Returns:
            (approved: bool, effective_command: str)
        """
        if self.always_allow_session:
            return True, command

        if self.is_safe_command(command):
            return True, command

        # Prompt user in terminal
        print(f"\n\033[1;33m⚠️  [GUARD INTERCEPT]\033[0m \033[1m{role}\033[0m wants to execute:")
        print(f"   \033[36mCommand:\033[0m {command}")
        if reason:
            print(f"   \033[90mReason:  {reason}\033[0m")

        try:
            choice = input("   \033[1;32m[Y]\033[0mes once | \033[1;34m[A]\033[0mlways session | \033[1;31m[N]\033[0mo deny | \033[1;35m[C]\033[0mustom: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\033[31mAction cancelled by user.\033[0m")
            return False, command

        if choice in ("y", ""):
            return True, command
        elif choice == "a":
            self.always_allow_session = True
            self.auto_approve = True
            print("\033[32m✔ Session permissions set to: Always Approve.\033[0m")
            return True, command
        elif choice == "c":
            custom_cmd = input("   Enter replacement command: ").strip()
            if custom_cmd:
                return True, custom_cmd
            return False, command
        else:
            print("\033[31m✖ Command execution denied.\033[0m")
            return False, command

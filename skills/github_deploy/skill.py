"""Skill: github_deploy

Automates Git initialization, GitHub repository creation, pushing, and enabling
GitHub Pages for free static web hosting.

Safety model
------------
This skill performs outward-facing, hard-to-reverse actions: creating a PUBLIC
GitHub repository, force-pushing over remote history, and publishing a site.
Every one of those requires an explicit opt-in via ``context["confirm"]``.

It also runs shell commands built partly from LLM-supplied strings, so no
subprocess is ever invoked through a shell. Arguments are passed as argv lists,
which removes the quoting/injection surface entirely (``shell=True`` with an
interpolated commit message was exploitable).

Three things this refuses to do without confirmation:
  * create a public repository
  * force-push over an existing remote branch
  * commit files that look like credentials
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

# Commands that require explicit human confirmation before running.
# Maps command name -> reason shown to the user.
CONFIRM_REQUIRED = {
    "repo_create": "create a PUBLIC GitHub repository",
    "force_push": "overwrite remote history with --force",
    "pages_enable": "publish a site publicly via GitHub Pages",
}

# Filenames that indicate a credential. Checked before `git add`, because after
# the commit the secret is in history and stays there.
SECRET_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials", ".npmrc", ".pypirc", "secrets.json", "service-account.json",
}
SECRET_PATTERNS = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|keystore)|id_(rsa|dsa|ecdsa|ed25519)|"
    r"credentials(\..*)?|\.netrc|\.htpasswd)$",
    re.IGNORECASE,
)


def _run(cmd: Sequence[str], cwd: Path, timeout: int = 120) -> Tuple[int, str, str]:
    """Run a command with an argv list. Never uses a shell.

    Returns (returncode, stdout, stderr).
    """
    env = os.environ.copy()
    # Augment PATH so per-user installs of git/gh are found, using os.pathsep
    # rather than a hardcoded ';' so this is correct on any platform.
    for candidate in (
        Path.home() / "AppData/Local/Programs/Git/cmd",
        Path("C:/Program Files/Git/cmd"),
        Path("C:/Program Files/GitHub CLI"),
        Path.home() / "AppData/Local/gh/bin",
    ):
        if candidate.exists():
            env["PATH"] = f"{candidate}{os.pathsep}{env.get('PATH', '')}"

    try:
        res = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            shell=False,  # argv list; no shell interpolation
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        return 127, "", f"Command not found: {cmd[0]} ({exc})"
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s: {cmd[0]}"

    return res.returncode, res.stdout.strip(), res.stderr.strip()


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _scan_for_secrets(workspace: Path) -> List[str]:
    """Return relative paths of files that look like credentials."""
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist"}
    suspicious: List[str] = []

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

        for name in files:
            rel = str(Path(root, name).relative_to(workspace)).replace("\\", "/")
            if name.lower() in SECRET_FILENAMES or SECRET_PATTERNS.search(rel):
                suspicious.append(rel)

    return sorted(suspicious)


def _is_inside_git_repo(workspace: Path) -> bool:
    """True if any ancestor of workspace is already a git work tree."""
    probe = workspace
    while True:
        if (probe / ".git").exists():
            return True
        if probe.parent == probe:
            return False
        probe = probe.parent


def _normalise_repo_name(raw: str) -> Optional[str]:
    """Validate a repository name against GitHub's rules.

    Rejects anything that is not a plain slug. The name reaches `gh` as an argv
    element (no shell), but a malformed name would still create a repo the user
    did not intend.
    """
    name = raw.strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", name):
        return None
    return name


def run(context: dict) -> dict:
    """Execute Git commit, GitHub push, and GitHub Pages activation.

    Args:
        context: dict with keys:
            - workspace: path to the website folder
            - repo_name: (optional) repository name (default: folder name)
            - commit_message: (optional) commit message
            - confirm: (optional) must be True to allow public creation,
              force-push, or enabling Pages. Without it, the skill reports what
              it *would* do and stops.
            - dry_run: (optional) if True, never contact GitHub.
    """
    workspace = Path(context.get("workspace", ".")).resolve()
    # Distinguish "not provided" from "provided but empty": `or` would silently
    # replace an explicit empty string with the folder default, so an invalid
    # name would never reach validation.
    provided_name = context.get("repo_name")
    repo_name_raw = (
        str(provided_name)
        if provided_name is not None
        else workspace.name.lower().replace(" ", "-")
    )
    commit_msg = context.get("commit_message") or "Deploy website via LC Agent"
    confirmed = context.get("confirm") is True
    dry_run = context.get("dry_run") is True

    logs: List[str] = []

    def respond(success: bool, **extra: Any) -> dict:
        return {"success": success, "logs": logs, **extra}

    # --- preflight ------------------------------------------------------

    if not workspace.is_dir():
        return respond(False, error=f"Workspace does not exist: {workspace}")

    if not (workspace / "index.html").exists():
        return respond(
            False,
            error=(
                "No index.html found in workspace. A root index.html is required "
                "for GitHub Pages."
            ),
        )

    repo_name = _normalise_repo_name(repo_name_raw)
    if repo_name is None:
        return respond(
            False,
            error=(
                f"Invalid repository name: {repo_name_raw!r}. Use letters, digits, "
                "dot, dash, or underscore (max 100 chars)."
            ),
        )

    for tool in ("git", "gh"):
        if not _which(tool):
            return respond(False, error=f"Required tool not found on PATH: {tool}")

    # Creating a nested repo inside an existing checkout is almost never intended.
    if not (workspace / ".git").exists() and _is_inside_git_repo(workspace):
        return respond(
            False,
            error=(
                f"{workspace} is inside an existing git repository. Initialising a "
                "nested repo would detach these files from the parent project's "
                "history. Move the site to its own directory, or run with an "
                "explicit .git already present."
            ),
        )

    secrets = _scan_for_secrets(workspace)
    if secrets:
        return respond(
            False,
            error=(
                "Refusing to deploy: credential-like files are present. Publishing "
                "these would expose them permanently in git history.\n  "
                + "\n  ".join(secrets)
            ),
            suspicious_files=secrets,
        )

    # --- report the plan before acting ----------------------------------

    plan = (
        f"repo    : {repo_name}\n"
        f"source  : {workspace}\n"
        f"public  : yes\n"
        f"pages   : yes\n"
        f"actions : git init, commit, create public repo, push, enable Pages"
    )

    if dry_run:
        logs.append("dry run -- no changes made")
        return respond(True, dry_run=True, plan=plan)

    needs_confirmation = not confirmed

    if needs_confirmation:
        logs.append("confirmation required; stopped before any remote change")
        return respond(
            False,
            needs_confirmation=True,
            plan=plan,
            error=(
                "This deployment is not yet approved. It would:\n\n"
                f"{plan}\n\n"
                "Re-run with confirm=True to proceed."
            ),
            confirmable_actions=[
                CONFIRM_REQUIRED["repo_create"],
                CONFIRM_REQUIRED["pages_enable"],
            ],
        )

    # --- local git ------------------------------------------------------

    if not (workspace / ".git").exists():
        code, out, err = _run(["git", "init", "-b", "main"], workspace)
        logs.append(f"git init: {out or err}")
        if code != 0:
            return respond(False, error=f"git init failed: {err}")

    # Only set identity if absent -- do not overwrite the user's own config.
    code, _, _ = _run(["git", "config", "user.name"], workspace)
    if code != 0:
        _run(["git", "config", "user.name", "dhisura"], workspace)
    code, _, _ = _run(["git", "config", "user.email"], workspace)
    if code != 0:
        _run(["git", "config", "user.email", "dhisura@users.noreply.github.com"], workspace)

    _run(["git", "add", "-A"], workspace)

    code, out, err = _run(["git", "status", "--porcelain"], workspace)
    if code == 0 and not out:
        logs.append("nothing to commit; working tree clean")
        return respond(False, error="No changes to deploy. Working tree is clean.")

    code, out, err = _run(["git", "commit", "-m", commit_msg], workspace)
    logs.append(f"git commit: {out or err}")
    if code != 0:
        return respond(False, error=f"git commit failed: {err or out}")

    # --- GitHub auth ----------------------------------------------------

    code, out, err = _run(["gh", "auth", "status"], workspace)
    if code != 0:
        return respond(False, error=f"GitHub CLI is not authenticated: {err}")

    username = ""
    for line in out.splitlines():
        if "Logged in to github.com account" in line:
            username = line.split("account", 1)[1].strip().split()[0]
            break
    if not username:
        return respond(
            False,
            error=f"Could not determine the authenticated GitHub user from: {out!r}",
        )

    # --- create or push -------------------------------------------------

    code, _, _ = _run(["gh", "repo", "view", f"{username}/{repo_name}"], workspace)

    if code != 0:
        logs.append(f"creating public repository {username}/{repo_name}")
        code, out, err = _run(
            ["gh", "repo", "create", repo_name, "--public", "--source=.", "--remote=origin", "--push"],
            workspace,
        )
        logs.append(f"gh repo create: {out or err}")
        if code != 0:
            return respond(False, error=f"gh repo create failed: {err or out}")
    else:
        logs.append(f"repository {username}/{repo_name} exists; pushing updates")
        code, out, err = _run(["git", "push", "-u", "origin", "main"], workspace)
        logs.append(f"git push: {out or err}")
        if code != 0:
            return respond(False, error=f"git push failed: {err or out}")

    # --- GitHub Pages ---------------------------------------------------

    code, out, err = _run(
        [
            "gh", "api", "-X", "POST",
            f"/repos/{username}/{repo_name}/pages",
            "-F", "build_type=legacy",
            "-F", "source[branch]=main",
            "-F", "source[path]=/",
        ],
        workspace,
    )
    combined = f"{out} {err}"
    if code != 0 and ("already has a GitHub Pages site" in combined or "already exists" in combined):
        logs.append("GitHub Pages already enabled")
    elif code != 0:
        # Not fatal: the repo and push succeeded, so report partial success
        # rather than a bare failure that hides what did work.
        logs.append(f"GitHub Pages activation failed: {err or out}")
        return respond(
            True,
            partial=True,
            repo_url=f"https://github.com/{username}/{repo_name}",
            live_url=None,
            error=(
                "Repository was created and pushed, but GitHub Pages could not be "
                f"enabled: {err or out}\nEnable it manually in Settings -> Pages."
            ),
        )

    return respond(
        True,
        repo_url=f"https://github.com/{username}/{repo_name}",
        live_url=f"https://{username}.github.io/{repo_name}/",
    )

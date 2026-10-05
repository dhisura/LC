"""Skill: github_deploy

Automates Git initialization, GitHub repository creation, pushing,
and enabling GitHub Pages for free static web hosting.
"""
import os
import subprocess
from pathlib import Path


def _run_cmd(cmd, cwd):
    """Helper to run a shell command and return output."""
    env = os.environ.copy()
    git_cmd_dir = str(Path.home() / "AppData/Local/Programs/Git/cmd")
    gh_bin_dir = str(Path.home() / "AppData/Local/gh/bin")
    env["PATH"] = f"{git_cmd_dir};{gh_bin_dir};{env.get('PATH', '')}"

    res = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        shell=True,
        env=env
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def run(context: dict) -> dict:
    """Executes Git commit, GitHub push, and GitHub Pages activation.
    
    Args:
        context: dict with keys:
            - workspace: path to the website folder
            - repo_name: (optional) name of the GitHub repository (defaults to folder name)
            - commit_message: (optional) commit message
    """
    workspace = Path(context.get("workspace", ".")).resolve()
    repo_name = context.get("repo_name", workspace.name.lower().replace(" ", "-"))
    commit_msg = context.get("commit_message", "Deploy website via LC Agent")

    logs = []

    # 1. Verify index.html exists
    if not (workspace / "index.html").exists():
        return {
            "success": False,
            "error": "No index.html found in workspace. A root index.html is required for GitHub Pages.",
            "logs": logs
        }

    # 2. Git Init
    if not (workspace / ".git").exists():
        code, out, err = _run_cmd("git init -b main", workspace)
        logs.append(f"git init: {out or err}")

    # Set git config if not set
    _run_cmd('git config user.name "dhisura"', workspace)
    _run_cmd('git config user.email "dhisura@users.noreply.github.com"', workspace)

    # 3. Git Add & Commit
    _run_cmd("git add .", workspace)
    code, out, err = _run_cmd(f'git commit -m "{commit_msg}"', workspace)
    logs.append(f"git commit: {out or err}")

    # 4. Check GitHub auth
    code, out, err = _run_cmd("gh auth status", workspace)
    if code != 0:
        return {
            "success": False,
            "error": f"GitHub CLI is not authenticated: {err}",
            "logs": logs
        }

    # Extract username (default dhisura)
    username = "dhisura"
    for line in out.splitlines():
        if "Logged in to github.com account" in line:
            parts = line.split("account")
            if len(parts) > 1:
                username = parts[1].strip().split()[0]

    # 5. Check if repo exists or create it
    code, out, err = _run_cmd(f"gh repo view {username}/{repo_name}", workspace)
    if code != 0:
        # Create new repo on GitHub and push
        logs.append(f"Creating new GitHub repository: {username}/{repo_name}...")
        create_cmd = f"gh repo create {repo_name} --public --source=. --remote=origin --push"
        code, out, err = _run_cmd(create_cmd, workspace)
        logs.append(f"gh repo create: {out or err}")
    else:
        # Push to existing repo
        logs.append(f"Repository {username}/{repo_name} already exists. Pushing updates...")
        code, out, err = _run_cmd("git push -u origin main --force", workspace)
        logs.append(f"git push: {out or err}")

    # 6. Enable GitHub Pages
    logs.append("Configuring GitHub Pages free hosting...")
    pages_cmd = f"gh api -X POST /repos/{username}/{repo_name}/pages -F build_type=legacy -F source[branch]=main -F source[path]=/"
    code, out, err = _run_cmd(pages_cmd, workspace)
    if "already has a GitHub Pages site" in err or "already exists" in err:
        logs.append("GitHub Pages is already active.")
    else:
        logs.append(f"GitHub Pages activation: {out or err}")

    live_url = f"https://{username}.github.io/{repo_name}/"
    repo_url = f"https://github.com/{username}/{repo_name}"

    return {
        "success": True,
        "repo_url": repo_url,
        "live_url": live_url,
        "logs": logs
    }

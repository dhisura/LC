"""Skill: git_cleaner

This module is auto-loaded by LC. Export a run() function
that agents can invoke during sprints.
"""


def run(context: dict) -> dict:
    """Execute this skill.

    Args:
        context: Dict with keys like "task", "workspace", "stack", "files".

    Returns:
        Dict with keys like "output", "success", "files_created".
    """
    # TODO: Implement your skill logic here
    return {"output": "Skill executed", "success": True}

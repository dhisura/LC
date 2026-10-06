"""Skill Plugin System for LC.

Skills are drop-in capability folders that live in ~/.lc/skills/ (or a custom path).
Each skill folder contains:
  - SKILL.md    : A markdown description of what the skill does (injected into agent prompts)
  - skill.py    : A Python module exporting a run() function the agents can call

Skills are auto-discovered at startup and made available to all roles.
"""
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from lc.config import LC_HOME, SKILLS_DIR


# NOTE: deliberately no mkdir at import time. Creating ~/.lc/skills as a side
# effect of `import lc.engine.skills` made read-only commands like
# `lc --models` mutate the filesystem. SkillManager creates it on demand.


def _bundled_skills_dir() -> Path:
    """Locate the ``skills/`` folder shipped inside the package, if present.

    Walks up from this file so it works from a source checkout, an editable
    install, and a wheel alike. Returns a non-existent path when running from an
    installed package that does not bundle one -- callers treat that as "no
    bundled skills" rather than an error.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "skills"
        if candidate.is_dir():
            return candidate
    return SKILLS_DIR


@dataclass
class Skill:
    """A single loaded skill plugin."""
    name: str
    description: str
    run: Optional[Callable] = None
    path: Path = field(default_factory=Path)

    def to_prompt_block(self) -> str:
        """Format skill as a context block for LLM injection."""
        return f"[SKILL: {self.name}]\n{self.description}\n[END SKILL]"


class SkillManager:
    """Discovers, loads, and manages skill plugins from the skills directory.

    Two directories are searched, in order:

    1. ``~/.lc/skills`` -- machine-local, where ``lc --new-skill`` scaffolds.
    2. ``<repo>/skills`` -- the bundled plugins that ship with the source.

    The second one matters: skills committed to the repo were previously never
    loaded by anything, because discovery only ever looked in ``~/.lc``. Entries
    in ``~/.lc`` win on name collision, so a user can override a bundled skill.
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.bundled_dir = _bundled_skills_dir()
        self.skills: Dict[str, Skill] = {}

    def _search_dirs(self) -> List[Path]:
        local = Path(self.skills_dir)
        bundled = Path(self.bundled_dir)
        if bundled == local:
            return [local]
        return [local, bundled]

    def discover(self) -> List[Skill]:
        """Auto-discover skill folders across the local and bundled dirs."""
        self.skills.clear()

        # Bundled first so that ~/.lc entries overwrite them on collision.
        for directory in reversed(self._search_dirs()):
            if not directory.exists():
                continue
            for folder in sorted(directory.iterdir()):
                if not folder.is_dir():
                    continue
                if folder.name.startswith("_") or folder.name.startswith("."):
                    continue

                skill = self._load_skill(folder)
                if skill:
                    self.skills[skill.name] = skill

        return list(self.skills.values())

    def _load_skill(self, folder: Path) -> Optional[Skill]:
        """Load a single skill from a folder."""
        name = folder.name
        description = ""
        run_fn = None

        # Read SKILL.md for the description
        skill_md = folder / "SKILL.md"
        if skill_md.exists():
            description = skill_md.read_text(encoding="utf-8", errors="replace").strip()
        else:
            # Fall back to any .md file
            md_files = list(folder.glob("*.md"))
            if md_files:
                description = md_files[0].read_text(encoding="utf-8", errors="replace").strip()

        if not description:
            description = f"Skill '{name}' (no description provided)"

        # Load skill.py if it exists
        skill_py = folder / "skill.py"
        if skill_py.exists():
            try:
                spec = importlib.util.spec_from_file_location(f"lc_skill_{name}", skill_py)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "run"):
                        run_fn = module.run
            except Exception as e:
                description += f"\n\n[WARNING: Failed to load skill.py: {e}]"

        return Skill(name=name, description=description, run=run_fn, path=folder)

    def get_prompt_context(self, stack: str = "", task: str = "") -> str:
        """Build a combined prompt block for all loaded skills."""
        if not self.skills:
            return ""

        blocks = []
        for skill in self.skills.values():
            blocks.append(skill.to_prompt_block())

        return "### AVAILABLE SKILLS:\n" + "\n\n".join(blocks)

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a specific skill by name."""
        return self.skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        """List all skills with metadata."""
        return [
            {
                "name": s.name,
                "has_runner": s.run is not None,
                "path": str(s.path),
                "description": s.description[:100]
            }
            for s in self.skills.values()
        ]

    @staticmethod
    def create_skill_template(name: str, skills_dir: Optional[Path] = None) -> Path:
        """Scaffold a new skill folder with SKILL.md and skill.py templates."""
        base = skills_dir or SKILLS_DIR
        folder = base / name
        folder.mkdir(parents=True, exist_ok=True)

        # Create SKILL.md template
        skill_md = folder / "SKILL.md"
        if not skill_md.exists():
            skill_md.write_text(
                f"# {name}\n\n"
                "## What This Skill Does\n"
                "Describe the capability this skill adds to the LC agent company.\n\n"
                "## When to Use\n"
                "Describe the trigger conditions: what kind of tasks or keywords activate this skill.\n\n"
                "## Instructions for Agents\n"
                "Provide clear directives that get injected into the agent's system prompt.\n",
                encoding="utf-8"
            )

        # Create skill.py template
        skill_py = folder / "skill.py"
        if not skill_py.exists():
            skill_py.write_text(
                f'"""Skill: {name}\n\n'
                'This module is auto-loaded by LC. Export a run() function\n'
                'that agents can invoke during sprints.\n"""\n\n\n'
                'def run(context: dict) -> dict:\n'
                '    """Execute this skill.\n\n'
                '    Args:\n'
                '        context: Dict with keys like "task", "workspace", "stack", "files".\n\n'
                '    Returns:\n'
                '        Dict with keys like "output", "success", "files_created".\n'
                '    """\n'
                '    # TODO: Implement your skill logic here\n'
                '    return {"output": "Skill executed", "success": True}\n',
                encoding="utf-8"
            )

        return folder

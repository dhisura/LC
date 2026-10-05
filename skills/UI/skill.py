```python
"""Skill: UI/UX

This module is auto-loaded by LC.
Exports a run() function that agents can invoke during sprints.

Purpose:
    Provide structured UI/UX reasoning, design directives, and quality
    checks for interface-related tasks.

The skill does not directly modify project files. It produces guidance
that the calling agent can use during planning, implementation, or review.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL_NAME = "ui-ux"
SKILL_VERSION = "1.0.0"

TRIGGER_KEYWORDS = {
    "ui",
    "ux",
    "interface",
    "frontend",
    "dashboard",
    "screen",
    "page",
    "component",
    "layout",
    "design",
    "redesign",
    "responsive",
    "accessibility",
    "design system",
    "interaction",
    "animation",
    "agent ui",
    "chat ui",
    "tool call",
    "approval",
    "workflow",
    "form",
    "table",
    "visualization",
}


# ---------------------------------------------------------------------------
# Core directives
# ---------------------------------------------------------------------------

CORE_DIRECTIVES = [
    "Understand the user's primary task before designing the interface.",
    "Establish information hierarchy before visual styling.",
    "Prefer purposeful UI over decorative UI.",
    "Reuse the existing design system when one exists.",
    "Design complete interaction states, not only the default state.",
    "For AI products, explicitly design agent states and human-in-the-loop flows.",
    "Preserve application context so users do not need to repeat known information.",
    "Use clear, specific, action-oriented UX copy.",
    "Design responsive behavior rather than simply shrinking desktop layouts.",
    "Address accessibility as part of implementation, not as a final patch.",
    "Use motion only when it communicates state, feedback, orientation, or continuity.",
    "Inspect the rendered interface when tooling permits.",
    "Separate design generation from quality evaluation.",
    "Do not equate anti-slop design with avoiding specific visual styles.",
]


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

QUALITY_GATES = [
    "primary_task",
    "information_hierarchy",
    "navigation",
    "primary_actions",
    "interaction_states",
    "agent_states",
    "loading_state",
    "empty_state",
    "error_state",
    "error_recovery",
    "responsive_behavior",
    "accessibility",
    "design_system_consistency",
    "ux_copy",
    "visual_hierarchy",
    "unnecessary_complexity",
    "generic_ai_patterns",
    "rendered_visual_review",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_context(context: dict[str, Any]) -> dict[str, Any]:
    """Normalize optional context fields without mutating the caller."""

    return {
        "task": str(context.get("task", "") or "").strip(),
        "workspace": context.get("workspace"),
        "stack": context.get("stack"),
        "files": context.get("files") or [],
        "mode": context.get("mode", "design"),
        "references": context.get("references") or [],
    }


def _task_matches(task: str) -> bool:
    """Return True when the task contains a UI/UX-related signal."""

    normalized = task.lower()

    return any(
        keyword in normalized
        for keyword in TRIGGER_KEYWORDS
    )


def _detect_focus(task: str) -> list[str]:
    """Determine the most relevant UI/UX areas from the task."""

    normalized = task.lower()
    focus: list[str] = []

    mappings = {
        "agent interaction": (
            "agent",
            "tool call",
            "approval",
            "permission",
            "human in the loop",
        ),
        "responsive": (
            "responsive",
            "mobile",
            "tablet",
            "breakpoint",
        ),
        "accessibility": (
            "accessibility",
            "accessible",
            "aria",
            "keyboard",
            "screen reader",
            "wcag",
        ),
        "data visualization": (
            "chart",
            "graph",
            "visualization",
            "analytics",
            "dashboard",
            "metrics",
        ),
        "design system": (
            "design system",
            "component",
            "token",
            "theme",
            "storybook",
        ),
        "interaction": (
            "interaction",
            "animation",
            "transition",
            "modal",
            "dialog",
            "form",
        ),
        "review": (
            "review",
            "audit",
            "improve",
            "fix",
            "critique",
            "redesign",
        ),
    }

    for area, keywords in mappings.items():
        if any(keyword in normalized for keyword in keywords):
            focus.append(area)

    if not focus:
        focus.append("general UX")

    return focus


def _build_directives(
    context: dict[str, Any],
    focus: list[str],
) -> list[str]:
    """Build task-specific directives."""

    directives = list(CORE_DIRECTIVES)

    if "agent interaction" in focus:
        directives.extend(
            [
                "Model relevant agent states such as planning, executing, "
                "waiting for approval, completed, failed, and retrying.",
                "Expose useful action, progress, result, and error information "
                "without exposing private chain-of-thought.",
                "Use explicit confirmation for consequential or irreversible "
                "actions.",
                "Prefer shared application actions between UI controls and "
                "agent tools.",
            ]
        )

    if "responsive" in focus:
        directives.extend(
            [
                "Define how hierarchy, navigation, tables, side panels, and "
                "actions change across viewport sizes.",
                "Do not solve responsive behavior by merely scaling desktop UI.",
            ]
        )

    if "accessibility" in focus:
        directives.extend(
            [
                "Use semantic HTML and appropriate ARIA.",
                "Ensure keyboard navigation and visible focus.",
                "Do not communicate important information using color alone.",
                "Respect reduced-motion preferences.",
            ]
        )

    if "data visualization" in focus:
        directives.extend(
            [
                "Choose visualization types based on the question being "
                "answered, not because a chart is expected.",
                "Use tables when exact values or dense operational data are "
                "more useful than charts.",
            ]
        )

    if "design system" in focus:
        directives.extend(
            [
                "Inspect existing tokens and components before creating new "
                "visual primitives.",
                "Do not create duplicate components when an existing component "
                "can satisfy the requirement.",
            ]
        )

    if "interaction" in focus:
        directives.extend(
            [
                "Define applicable default, hover, focus, active, selected, "
                "disabled, loading, success, and error states.",
                "Use animation only when it communicates feedback, state, "
                "orientation, or continuity.",
            ]
        )

    if "review" in focus:
        directives.extend(
            [
                "Evaluate the actual rendered interface when tooling permits.",
                "Look for unnecessary cards, decorative effects, generic SaaS "
                "patterns, inconsistent spacing, weak hierarchy, and missing "
                "edge states.",
            ]
        )

    return directives


def _build_quality_checklist(
    context: dict[str, Any],
    focus: list[str],
) -> list[dict[str, Any]]:
    """Create a machine-readable quality checklist."""

    checks = []

    for gate in QUALITY_GATES:
        required = True

        if gate == "agent_states":
            required = "agent interaction" in focus

        if gate == "rendered_visual_review":
            required = bool(context.get("workspace"))

        checks.append(
            {
                "id": gate,
                "required": required,
                "status": "pending",
            }
        )

    return checks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(context: dict[str, Any]) -> dict[str, Any]:
    """Execute the UI/UX skill.

    Args:
        context:
            Dict containing information such as:
                - task
                - workspace
                - stack
                - files
                - mode
                - references

    Returns:
        Structured UI/UX guidance for the calling agent.
    """

    if not isinstance(context, dict):
        return {
            "output": "Invalid skill context: expected a dictionary.",
            "success": False,
            "files_created": [],
        }

    normalized = _normalize_context(context)
    task = normalized["task"]

    # Do not interfere with unrelated tasks.
    if not task:
        return {
            "output": "No task provided. UI/UX skill not executed.",
            "success": False,
            "files_created": [],
        }

    if not _task_matches(task):
        return {
            "output": (
                "Task does not contain a strong UI/UX signal. "
                "UI/UX skill not activated."
            ),
            "success": True,
            "files_created": [],
            "activated": False,
        }

    focus = _detect_focus(task)
    directives = _build_directives(normalized, focus)
    quality_checks = _build_quality_checklist(normalized, focus)

    return {
        "skill": SKILL_NAME,
        "version": SKILL_VERSION,
        "success": True,
        "activated": True,
        "files_created": [],
        "output": {
            "task": task,
            "mode": normalized["mode"],
            "focus": focus,
            "directives": directives,
            "quality_checks": quality_checks,
            "workflow": [
                "understand_product",
                "define_information_architecture",
                "design_interaction",
                "apply_design_system",
                "implement",
                "evaluate_accessibility",
                "inspect_rendered_ui",
                "run_ux_visual_anti_slop_audit",
                "fix_issues",
                "final_quality_gate",
            ],
        },
    }
```

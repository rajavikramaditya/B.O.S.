"""Owner run contract — first-class goal/plan/verify object (ADR-012).

Neena is a separate agent product; runs manage external systems via tools.
"""
from __future__ import annotations

from typing import Any, TypedDict


class OwnerRun(TypedDict, total=False):
    goal: str
    action: str
    slots: dict[str, Any]
    success_criteria: str
    plan_steps: list[str]
    tools_needed: list[str]
    tools_available: list[str]
    tools_missing: list[str]
    observations: list[dict[str, Any]]
    verification: dict[str, Any]
    status: str  # planned|running|needs_confirm|verified|failed|cannot
    factual_packet: dict[str, Any]


def new_run(
    *,
    goal: str,
    action: str,
    slots: dict[str, Any] | None = None,
    success_criteria: str = "",
) -> OwnerRun:
    return {
        "goal": (goal or "")[:500],
        "action": (action or "").strip().lower(),
        "slots": dict(slots or {}),
        "success_criteria": success_criteria or f"action {action} executed with evidence",
        "plan_steps": [],
        "tools_needed": [],
        "tools_available": [],
        "tools_missing": [],
        "observations": [],
        "verification": {},
        "status": "planned",
        "factual_packet": {},
    }


__all__ = ["OwnerRun", "new_run"]

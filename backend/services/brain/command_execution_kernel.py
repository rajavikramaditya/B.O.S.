"""M4-A8.5 / M4-A8.5.2 — Structured action registry (no natural-language routing).

Action membership and aliases now derive from neena_tool_catalog.
"""
from __future__ import annotations

from typing import Any


def normalize_action_key(action: str) -> str:
    """Normalize dashboard / model action ids to executor keys."""
    from services.tools.catalog import normalize_tool_id

    return normalize_tool_id(action) or (action or "").strip().lower()


def __getattr__(name: str):
    from services.tools.catalog import (
        action_ids,
        cockpit_ids,
        creative_ids,
        live_ops_ids,
    )

    if name == "KERNEL_LOCAL_ACTIONS":
        # Historical set ≈ cockpit + live_ops reads used by ops router
        return live_ops_ids() | cockpit_ids()
    if name == "CREATIVE_KERNEL_ACTIONS":
        return creative_ids()
    if name == "ALL_STRUCTURED_ACTIONS":
        return action_ids() | frozenset({"unknown"})
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def is_valid_structured_action(action: str) -> bool:
    from services.tools.catalog import valid_actions_with_unknown

    return normalize_action_key(action) in valid_actions_with_unknown()


def resolve_local_command(message: str) -> dict[str, Any] | None:
    """
    M4-A8.5.2 — Natural-language routing removed.
    Owner text must go through the model command interpreter; use explicit action_id for buttons.
    """
    del message
    return None


__all__ = [
    "ALL_STRUCTURED_ACTIONS",
    "CREATIVE_KERNEL_ACTIONS",
    "KERNEL_LOCAL_ACTIONS",
    "is_valid_structured_action",
    "normalize_action_key",
    "resolve_local_command",
]

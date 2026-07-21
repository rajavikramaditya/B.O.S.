"""Live-ops catalog bridge (ADR-013 Wave 2).

Hands bodies live under services.tools.live_ops.*.
This module only exposes try_execute / dispatch compat + LIVE_OPS_ACTIONS.
"""
from __future__ import annotations

from services.brain.live_state_snapshot import build_neena_live_state_snapshot


def _live_ops_action_ids() -> frozenset:
    from services.tools.catalog import live_ops_ids

    return live_ops_ids()


def dispatch_live_ops_action(
    action: str,
    slots: dict | None,
    *,
    snapshot: dict | None = None,
    owner_message: str = "",
) -> dict | None:
    """Compat: run via catalog.execute (handlers bound in live_ops.bind_all)."""
    from services.tools.catalog import ToolContext, execute, get, normalize_tool_id

    action = normalize_tool_id(action)
    slots = dict(slots or {})
    snap = snapshot or build_neena_live_state_snapshot()
    spec = get(action)
    if spec is None or spec.route != "live_ops":
        return None
    return execute(
        action,
        ToolContext(
            action=action,
            slots=slots,
            snapshot=snap,
            owner_message=owner_message or "",
        ),
    )


def try_execute_live_ops(
    action: str,
    slots: dict | None,
    *,
    snapshot: dict | None = None,
    owner_message: str = "",
) -> dict | None:
    """Run structured live ops via the tool catalog."""
    return dispatch_live_ops_action(
        action, slots, snapshot=snapshot, owner_message=owner_message
    )


def __getattr__(name: str):
    if name == "LIVE_OPS_ACTIONS":
        return _live_ops_action_ids()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LIVE_OPS_ACTIONS", "dispatch_live_ops_action", "try_execute_live_ops"]

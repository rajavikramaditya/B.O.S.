"""Example plug-and-play read tool — register only; no allowlist edits.

Imported from services.tools.load_all(). Proves DX: new module + ToolSpec = live.
"""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register


def _handle_catalog_health(ctx: ToolContext) -> dict[str, Any] | None:
    from services.tools.catalog import action_ids, followup_ids

    del ctx
    ids = sorted(action_ids())
    follow = sorted(followup_ids())
    packet = {
        "tool": "catalog_health",
        "status": "ok",
        "tool_count": len(ids),
        "followup_count": len(follow),
        "sample_tools": ids[:8],
    }
    return build_live_ops_result(
        "CATALOG_HEALTH",
        packet=packet,
        fallback_line=f"Tool catalog healthy: {len(ids)} tools, {len(follow)} followup-safe.",
    )


def register_catalog_health() -> None:
    """Idempotent register — safe to call on every load_all()."""
    register(
        ToolSpec(
            id="catalog_health",
            description="Report tool catalog membership (plug-and-play health check)",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="status",
            handler=_handle_catalog_health,
        )
    )

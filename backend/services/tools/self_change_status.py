"""Plug-and-play read tool — self-change / capability inventory status.

Register only; interpreter enum derives from catalog (ADR-007 / ADR-010).
"""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register


def _handle_self_change_status(ctx: ToolContext) -> dict[str, Any] | None:
    del ctx
    from services.memory.self_change import format_change_recall

    recall = format_change_recall()
    packet = recall.get("factual_packet") if isinstance(recall.get("factual_packet"), dict) else {}
    return build_live_ops_result(
        recall.get("action_type") or "SELF_CHANGE_STATUS",
        packet=packet,
        fallback_line=recall.get("fallback_line") or "Self-change status unavailable.",
        ok=bool(recall.get("ok")),
        factual_packet=packet,
    )


def register_self_change_status() -> None:
    register(
        ToolSpec(
            id="self_change_status",
            description=(
                "Report Neena capability changes after restart "
                "(tools/flags added, removed, or pending announce)"
            ),
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="status",
            capability_label="Self-change / restart capability status",
            handler=_handle_self_change_status,
        )
    )

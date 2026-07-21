"""Plug-and-play owner tool: recall customer WhatsApp threads (checked facts).

Interpreter classifies → catalog handler → recorder/Redis helpers.
No Hindi/Hinglish phrase NLU in brain.
"""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register


def _handle_customer_whatsapp_recall(ctx: ToolContext) -> dict[str, Any] | None:
    from services.brain import feature_flags
    from services.brain.owner_customer_context import build_customer_recall_packet

    if not feature_flags.owner_customer_context_enabled():
        return build_live_ops_result(
            "CUSTOMER_WHATSAPP_RECALL",
            packet={
                "tool": "customer_whatsapp_recall",
                "status": "disabled",
                "checked": False,
                "reason": "NEENA_OWNER_CUSTOMER_CONTEXT off",
            },
            fallback_line="Customer WhatsApp recall is disabled by flag.",
        )

    slots = ctx.slots or {}
    phone = str(slots.get("phone_digits") or slots.get("phone") or "").strip()
    date_ist = str(slots.get("date_ist") or "").strip()
    window = str(slots.get("window") or "").strip()
    try:
        limit = int(slots.get("limit") or 40)
    except (TypeError, ValueError):
        limit = 40
    limit = max(10, min(limit, 80))

    out = build_customer_recall_packet(
        phone_digits=phone,
        owner_message=ctx.owner_message or "",
        limit=limit,
        date_ist=date_ist,
        window=window,
    )
    return build_live_ops_result(
        out.get("action_type") or "CUSTOMER_WHATSAPP_RECALL",
        packet=out.get("factual_packet")
        or {"tool": "customer_whatsapp_recall", "status": "empty", "checked": True},
        fallback_line=out.get("fallback_line") or "Customer WhatsApp recall checked.",
    )


def register_customer_whatsapp_tools() -> None:
    register(
        ToolSpec(
            id="customer_whatsapp_recall",
            description=(
                "Recall customer/listener WhatsApp for an IST day window (default today) "
                "from Command Center recorder whatsapp_listener + optional Redis thread "
                "if phone_digits given. Returns contacts roster. Read-only. "
                "Use when owner asks if any customer messaged, kis kis se baat hui, "
                "lead/inquiry status, or what a listener said. "
                "Slots: phone_digits?, date_ist? (YYYY-MM-DD), window? (today|yesterday), limit?."
            ),
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Customer WhatsApp recall",
            handler=_handle_customer_whatsapp_recall,
        )
    )


__all__ = ["register_customer_whatsapp_tools"]

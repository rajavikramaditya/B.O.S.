"""Plug-and-play tool: arm deferred WhatsApp status (ADR-007 / ADR-012 W3).

Register only — no frozenset / bind_handlers edits.
"""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register


def _handle_arm_deferred_status(ctx: ToolContext) -> dict[str, Any] | None:
    from services.cockpit.deferred_status import arm_deferred_status

    result = arm_deferred_status(message=ctx.owner_message or "", slots=ctx.slots)
    ok = bool(result.get("ok"))
    status = result.get("status") or ("armed" if ok else "cannot")
    packet = {
        "tool": "arm_deferred_status",
        **{k: v for k, v in result.items() if k != "ok"},
        "status": status,
    }
    if ok:
        line = (
            f"Deferred WhatsApp status ARMED: job={result.get('job_id')}; "
            f"delay_seconds={result.get('delay_seconds')}; kind={result.get('status_kind')}; "
            f"due_at={result.get('due_at')}. Worker will push one message — not a fake timer claim."
        )
        return build_live_ops_result("DEFERRED_STATUS_ARMED", packet=packet, fallback_line=line)
    if status == "busy":
        line = (
            f"Cannot arm: pending deferred job already exists "
            f"(id={result.get('existing_job_id')}, due={result.get('due_at')}). Max 1."
        )
        return build_live_ops_result("DEFERRED_STATUS_BUSY", packet=packet, fallback_line=line)
    line = (
        f"Cannot: deferred status worker not armed "
        f"({result.get('reason') or 'unavailable'})."
    )
    return build_live_ops_result("DEFERRED_STATUS_CANNOT", packet=packet, fallback_line=line)


def register_arm_deferred_status() -> None:
    register(
        ToolSpec(
            id="arm_deferred_status",
            description=(
                "Arm exactly one deferred WhatsApp status push after N minutes "
                "(worker delivers fresh tool facts; never invent timer success)"
            ),
            risk="read",  # arming is reversible / no Azura write; delivery is side-effect of worker
            route="live_ops",
            followup_ok=False,
            category="status",
            aliases=("schedule_deferred_status", "deferred_whatsapp_status"),
            slot_hint="delay_minutes (optional), status_kind (vm_status|now_playing|bundle)",
            capability_label="Deferred WhatsApp status (armed worker)",
            handler=_handle_arm_deferred_status,
        )
    )

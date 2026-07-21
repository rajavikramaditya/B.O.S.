"""Radio hands: living Station Clock plan (not capsule show-plan)."""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register
from services.tools import station_plan_store as store


def _flag_on() -> bool:
    try:
        import services.brain.feature_flags as feature_flags

        return feature_flags.station_plan_enabled()
    except Exception:
        return True


def _set_wc_plan_id(plan_id: str) -> None:
    try:
        from services.agent.working_context import load_working_context
        from services.brain import redis_state

        ctx = dict(load_working_context() or {})
        ctx["active_plan_id"] = plan_id
        redis_state.save_owner_working_context(ctx)
    except Exception:
        pass


def _format_plan_line(plan: dict[str, Any]) -> str:
    blocks = plan.get("blocks") or []
    pending = sum(1 for b in blocks if isinstance(b, dict) and b.get("status") == "pending")
    drafted = sum(1 for b in blocks if isinstance(b, dict) and b.get("status") == "drafted")
    nxt = store.next_pending_block(plan)
    nxt_s = f" Next: {nxt.get('title')} ({nxt.get('kind')})." if nxt else " No pending blocks."
    return (
        f"Station Clock plan {plan.get('plan_id')} "
        f"{plan.get('window_start')}→{plan.get('window_end')} IST — "
        f"{len(blocks)} blocks ({pending} pending, {drafted} drafted).{nxt_s}"
    )


def _handle_create(ctx: ToolContext) -> dict[str, Any] | None:
    if not _flag_on():
        return build_live_ops_result(
            "STATION_PLAN_DISABLED",
            packet={"tool": "create_station_plan", "status": "disabled"},
            fallback_line="Station plan hand disabled (NEENA_STATION_PLAN).",
        )
    slots = ctx.slots or {}
    horizon = str(slots.get("horizon") or slots.get("window") or "shift_4h").strip().lower()
    if horizon in ("3h", "3", "shift_3"):
        horizon = "shift_3h"
    if horizon in ("4h", "4", "shift_4", "evening", "show"):
        horizon = "shift_4h"
    if horizon in ("day", "aaj", "24h"):
        horizon = "day"
    theme = str(slots.get("theme") or slots.get("show_type") or "")[:120]
    hours = slots.get("hours")
    try:
        hours_i = int(hours) if hours is not None else None
    except (TypeError, ValueError):
        hours_i = None
    plan = store.build_shift_clock_plan(horizon=horizon, hours=hours_i, theme=theme)
    store.save_plan(plan)
    _set_wc_plan_id(str(plan["plan_id"]))
    line = _format_plan_line(plan) + " Living plan — not a Lab show_plan capsule."
    return build_live_ops_result(
        "STATION_PLAN_CREATED",
        packet={"tool": "create_station_plan", "status": "ok", "plan": plan},
        fallback_line=line,
    )


def _handle_get(ctx: ToolContext) -> dict[str, Any] | None:
    del ctx
    plan = store.load_plan()
    if not plan:
        return build_live_ops_result(
            "STATION_PLAN_EMPTY",
            packet={"tool": "get_station_plan", "status": "empty"},
            fallback_line="Sir, abhi koi active Station Clock plan nahi hai. Pehle create_station_plan chalao.",
        )
    return build_live_ops_result(
        "STATION_PLAN",
        packet={"tool": "get_station_plan", "status": "ok", "plan": plan},
        fallback_line=_format_plan_line(plan),
    )


def _handle_advance(ctx: ToolContext) -> dict[str, Any] | None:
    plan = store.load_plan()
    if not plan:
        return _handle_get(ctx)
    slots = ctx.slots or {}
    block_id = str(slots.get("block_id") or "").strip()
    status = str(slots.get("status") or "done").strip().lower()
    if status not in ("done", "skipped", "pending", "drafted"):
        status = "done"
    if not block_id:
        nxt = store.next_pending_block(plan)
        block_id = str((nxt or {}).get("id") or "")
    if not block_id:
        return build_live_ops_result(
            "STATION_PLAN_EMPTY",
            packet={"tool": "advance_station_plan", "status": "empty"},
            fallback_line="Sir, advance ke liye koi pending block nahi.",
        )
    patched = store.patch_block(plan, block_id, status=status)
    if not patched:
        return build_live_ops_result(
            "STATION_PLAN_BLOCK_MISS",
            packet={"tool": "advance_station_plan", "status": "cannot", "block_id": block_id},
            fallback_line=f"Sir, block {block_id} plan me nahi mila.",
        )
    store.save_plan(plan)
    return build_live_ops_result(
        "STATION_PLAN_ADVANCED",
        packet={"tool": "advance_station_plan", "status": "ok", "block": patched, "plan_id": plan.get("plan_id")},
        fallback_line=f"Block {patched.get('title')} → {status}. {_format_plan_line(plan)}",
    )


def _handle_draft(ctx: ToolContext) -> dict[str, Any] | None:
    """Draft next (or named) pending block into a real script capsule via creative hand."""
    if not _flag_on():
        return _handle_create(ctx)  # will report disabled via create path if off
    plan = store.load_plan()
    if not plan:
        return build_live_ops_result(
            "STATION_PLAN_EMPTY",
            packet={"tool": "draft_plan_block", "status": "empty"},
            fallback_line="Sir, pehle Station Clock plan banao, phir draft.",
        )
    slots = ctx.slots or {}
    block_id = str(slots.get("block_id") or "").strip()
    block = None
    if block_id:
        for b in plan.get("blocks") or []:
            if isinstance(b, dict) and b.get("id") == block_id:
                block = b
                break
    else:
        block = store.next_pending_block(plan)
    if not block:
        return build_live_ops_result(
            "STATION_PLAN_EMPTY",
            packet={"tool": "draft_plan_block", "status": "empty"},
            fallback_line="Sir, draft ke liye koi pending block nahi.",
        )

    kind = str(block.get("kind") or "rj_intro")
    title = str(block.get("title") or kind)
    owner_msg = (
        f"Station Clock block draft: {title} (kind={kind}). "
        f"Write a fresh on-air talk link script for Orai Radio, ~90-150 words unless owner asked longer. "
        f"Clean Hinglish, broadcast-ready. Owner: {ctx.owner_message or ''}"
    )
    # Map kind → creative intent
    intent = "rj_intro"
    if kind in ("ad",):
        intent = "ad_script"
    elif kind in ("comedy", "mandi_or_local", "teaser", "rj_intro"):
        intent = "create_broadcast_capsule" if kind != "rj_intro" else "rj_intro"

    try:
        from services.brain import operations_workflows
        from services.brain.trace_builder import _TraceBuilder

        tb = _TraceBuilder()
        slots: dict[str, Any] = {}
        if intent == "ad_script":
            slots["duration_seconds"] = 30
        interp = {"action": intent, "slots": slots, "confidence": 0.9}
        result = operations_workflows.try_handle_interpreter_packet(
            message=owner_msg,
            interpreter_packet=interp,
            selected_model="auto",
            mem_packet={},
            mem_context="",
            tb=tb,
            force_sync=True,
        )
    except Exception as exc:
        return build_live_ops_result(
            "STATION_PLAN_DRAFT_FAIL",
            packet={"tool": "draft_plan_block", "status": "cannot", "detail": str(exc)[:200]},
            fallback_line=f"Sir, block draft fail: {type(exc).__name__}.",
        )

    if not isinstance(result, dict) or not result.get("reply"):
        return build_live_ops_result(
            "STATION_PLAN_DRAFT_FAIL",
            packet={"tool": "draft_plan_block", "status": "cannot", "block_id": block.get("id")},
            fallback_line="Sir, creative hand ne is block ke liye script nahi di.",
        )

    capsule_id = result.get("capsule_id")
    store.patch_block(
        plan,
        str(block["id"]),
        status="drafted" if capsule_id else "pending",
        capsule_id=capsule_id,
        notes=f"drafted via {intent}",
    )
    store.save_plan(plan)
    line = (
        f"Block '{title}' draft ready"
        + (f" — capsule #{capsule_id}" if capsule_id else "")
        + f". {_format_plan_line(plan)}"
    )
    return build_live_ops_result(
        "STATION_PLAN_DRAFT",
        packet={
            "tool": "draft_plan_block",
            "status": "ok" if capsule_id else "partial",
            "block_id": block.get("id"),
            "capsule_id": capsule_id,
            "plan_id": plan.get("plan_id"),
            "script_preview": str(result.get("reply") or "")[:400],
        },
        fallback_line=line,
    )


def register_station_plan_tools() -> None:
    register(
        ToolSpec(
            id="create_station_plan",
            description=(
                "Create living Station Clock plan for next 3–4h (or day chunks): "
                "talk-link blocks only; AutoDJ music separate. NOT a Lab show_plan capsule. "
                "Slots: horizon (shift_3h|shift_4h|day), theme?, hours?"
            ),
            risk="safe_write",
            route="live_ops",
            followup_ok=False,
            category="broadcast",
            aliases=("create_daily_show_plan", "daily_show_plan", "station_clock_plan"),
            slot_hint="horizon (shift_3h|shift_4h|day), theme?, hours?",
            capability_label="Station Clock plan (living)",
            handler=_handle_create,
        )
    )
    register(
        ToolSpec(
            id="get_station_plan",
            description="Read active Station Clock plan + block statuses",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="broadcast",
            aliases=("show_station_plan", "station_plan_status"),
            capability_label="Get Station Clock plan",
            handler=_handle_get,
        )
    )
    register(
        ToolSpec(
            id="advance_station_plan",
            description="Mark a Station Clock block done/skipped (default: next pending)",
            risk="safe_write",
            route="live_ops",
            category="broadcast",
            slot_hint="block_id?, status (done|skipped)",
            capability_label="Advance Station Clock block",
            handler=_handle_advance,
        )
    )
    register(
        ToolSpec(
            id="draft_plan_block",
            description=(
                "Draft next (or named) pending Station Clock block into a real script capsule "
                "via creative hands; attach capsule_id on the plan block"
            ),
            risk="safe_write",
            route="live_ops",
            category="broadcast",
            slot_hint="block_id?",
            capability_label="Draft next plan block → capsule",
            handler=_handle_draft,
        )
    )


__all__ = ["register_station_plan_tools"]

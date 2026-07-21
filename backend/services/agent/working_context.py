"""Owner working context — Cursor-like short-term scratchpad (Phase 1).

Stores last actions, pending confirm snapshot, job/capsule ids for continuity.
Redis primary; in-process fallback when Redis is down (local/dev).
Never stores secrets, unlock phrases, or full prompts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import services.brain.feature_flags as feature_flags
import services.brain.redis_state as redis_state

_FALLBACK: dict[str, Any] = {}
_MAX_RECENT = 5
_CLIP = 160


def _clip(text: Any, n: int = _CLIP) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def load_working_context() -> dict[str, Any]:
    if not feature_flags.owner_working_context_enabled():
        return {}
    # Redis-first (ADR-008): process mirror must not mask newer Redis across restarts.
    got = redis_state.get_owner_working_context()
    if got.get("success"):
        ctx = got.get("context")
        if isinstance(ctx, dict) and ctx:
            _FALLBACK.clear()
            _FALLBACK.update(ctx)
            return dict(ctx)
        # Redis up but empty — clear stale local so we don't resurrect old WC.
        if got.get("available", True) is not False:
            _FALLBACK.clear()
            return {}
    if _FALLBACK:
        return dict(_FALLBACK)
    return {}


def format_working_context_block(ctx: dict[str, Any] | None = None) -> str:
    """Compact block for interpreter / conversation prompts."""
    if not feature_flags.owner_working_context_enabled():
        return ""
    data = ctx if isinstance(ctx, dict) else load_working_context()
    if not data:
        return "OWNER WORKING CONTEXT: (empty this session)"
    lines = ["OWNER WORKING CONTEXT (short-term scratchpad — use for follow-ups):"]
    if data.get("open_goal"):
        lines.append(f"- open_goal: {data['open_goal']}")
    if data.get("last_intention_id"):
        lines.append(
            f"- last_intention_id: {data['last_intention_id']} "
            f"thread={data.get('last_thread_key') or '-'}"
        )
    if data.get("last_day_query"):
        lines.append(
            f"- last_day_query: {data['last_day_query']} "
            f"date_ist={data.get('last_day_date_ist') or '-'}"
        )
    if data.get("last_action_type"):
        lines.append(
            f"- last_action: {data.get('last_action_type')} route={data.get('last_route') or '-'}"
        )
    if data.get("last_user_message"):
        lines.append(f"- last_user: {data['last_user_message']}")
    if data.get("last_assistant_reply"):
        lines.append(f"- last_assistant: {data['last_assistant_reply']}")
    pending = data.get("pending")
    if isinstance(pending, dict) and pending:
        lines.append(
            f"- pending_confirm: type={pending.get('action_type')} "
            f"memory_id={pending.get('memory_id')} capsule_id={pending.get('capsule_id')}"
        )
    else:
        lines.append("- pending_confirm: none")
    if data.get("last_job_id"):
        lines.append(f"- last_job_id: {data['last_job_id']}")
    if data.get("last_capsule_id"):
        lines.append(f"- last_capsule_id: {data['last_capsule_id']}")
    if data.get("last_loop_step_count"):
        lines.append(f"- last_agent_loop_steps: {data['last_loop_step_count']}")
    loop_actions = data.get("last_loop_actions") or []
    if loop_actions:
        lines.append(f"- last_loop_actions: {', '.join(str(a) for a in loop_actions[-5:])}")
    recent = data.get("recent_actions") or []
    if recent:
        bits = [
            f"{r.get('action_type') or '?'}"
            for r in recent[-_MAX_RECENT:]
            if isinstance(r, dict)
        ]
        if bits:
            lines.append(f"- recent_actions: {', '.join(bits)}")
    return "\n".join(lines)


def update_working_context_after_turn(
    *,
    message: str,
    reply: str,
    action_type: str | None = None,
    route: str | None = None,
    tb: Any = None,
    require_confirmation: bool = False,
    job_id: str | None = None,
    factual_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge this turn into scratchpad. Safe fields only."""
    if not feature_flags.owner_working_context_enabled():
        return {}
    prev = load_working_context()
    recent = list(prev.get("recent_actions") or [])
    if action_type:
        recent.append(
            {
                "action_type": str(action_type),
                "route": str(route or "")[:80] or None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
    recent = recent[-_MAX_RECENT:]

    pending: dict[str, Any] | None = None
    try:
        from services.memory.edit_service import get_pending_memory_edit
        import services.memory.service as memory_service

        edit_p = get_pending_memory_edit()
        cand = memory_service.get_pending_permanent_memory_candidate()
        if edit_p:
            pending = {
                "action_type": "memory_edit",
                "memory_id": edit_p.get("memory_id"),
                "operation": edit_p.get("operation"),
                "status": "pending_owner_confirmation",
            }
        elif cand:
            pending = {
                "action_type": "permanent_memory_candidate",
                "status": "pending_owner_confirmation",
            }
    except Exception:
        pending = None
    if pending is None and (
        require_confirmation or (tb is not None and getattr(tb, "pending_action_snapshot", None))
    ):
        snap = getattr(tb, "pending_action_snapshot", None) if tb is not None else None
        if isinstance(snap, dict) and snap:
            pending = {
                "action_type": snap.get("action_type") or action_type,
                "capsule_id": snap.get("capsule_id"),
                "memory_id": snap.get("memory_id"),
                "status": snap.get("status"),
            }
        elif require_confirmation:
            pending = {"action_type": action_type, "status": "pending_owner_confirmation"}

    resolved_job = job_id
    if not resolved_job and tb is not None:
        resolved_job = getattr(tb, "job_id", None)
    if not resolved_job:
        import re as _re

        m = _re.search(r"\b(job_[a-f0-9]+)\b", reply or "", _re.I)
        if not m:
            m = _re.search(r"job(?:\s*id)?[:\s]+([a-zA-Z0-9_-]{6,})", reply or "", _re.I)
        if m:
            resolved_job = m.group(1)
    capsule_id = None
    if tb is not None:
        capsule_id = getattr(tb, "capsule_id_resolved", None) or getattr(tb, "capsule_id", None)

    open_goal = prev.get("open_goal")
    at = (action_type or "").upper()
    if at in ("MANAGE_MEMORY", "PROPOSE_PERMANENT_MEMORY") and require_confirmation:
        open_goal = f"confirm_{at.lower()}"
    elif at in ("PERMANENT_MEMORY_SAVE", "MEMORY_EDIT_APPLIED", "PERMANENT_MEMORY_CANCEL", "MEMORY_EDIT_CANCEL"):
        open_goal = None
    elif resolved_job and at in ("STREAM_VERIFY", "ENSURE_PLAYBACK"):
        open_goal = f"await_job:{resolved_job}"

    last_intention_id = prev.get("last_intention_id")
    last_thread_key = prev.get("last_thread_key")
    last_day_query = prev.get("last_day_query")
    last_day_date_ist = prev.get("last_day_date_ist")
    fp = factual_packet if isinstance(factual_packet, dict) else None
    if fp:
        tool = (fp.get("tool") or "").strip()
        if tool in ("future_intention_save", "future_intention_lifecycle", "future_intention_recall"):
            mid = fp.get("memory_id")
            if mid is not None:
                last_intention_id = mid
                open_goal = f"intention:{mid}"
            if fp.get("thread_key"):
                last_thread_key = str(fp.get("thread_key"))
            if at in ("FUTURE_INTENTION_COMPLETE", "FUTURE_INTENTION_CANCEL"):
                open_goal = None
            elif at == "FUTURE_INTENTION_POSTPONE" and mid is not None:
                open_goal = f"intention:{mid}"
        if tool == "day_memory_recall":
            last_day_query = _clip(message, 80)
            last_day_date_ist = fp.get("date_ist") or fp.get("label")
            if fp.get("date_ist"):
                open_goal = f"day:{fp.get('date_ist')}"

    loop_step_count = prev.get("last_loop_step_count")
    loop_actions = list(prev.get("last_loop_actions") or [])
    if fp and fp.get("tool") == "agent_loop":
        loop_step_count = int(fp.get("step_count") or 0) or None
        loop_actions = [
            str(s.get("action"))
            for s in (fp.get("steps") or [])
            if isinstance(s, dict) and s.get("action")
        ][-5:]

    ctx = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_action_type": action_type,
        "last_route": route,
        "last_user_message": _clip(message),
        "last_assistant_reply": _clip(reply),
        "pending": pending,
        "last_job_id": resolved_job or prev.get("last_job_id"),
        "last_capsule_id": capsule_id or prev.get("last_capsule_id"),
        "open_goal": open_goal,
        "last_intention_id": last_intention_id,
        "last_thread_key": last_thread_key,
        "last_day_query": last_day_query,
        "last_day_date_ist": last_day_date_ist,
        "recent_actions": recent,
        "last_loop_step_count": loop_step_count,
        "last_loop_actions": loop_actions,
    }
    saved = redis_state.save_owner_working_context(ctx)
    # Always keep process-local mirror so same-request follow-ups work if Redis lags.
    _FALLBACK.clear()
    _FALLBACK.update(ctx)
    if not saved.get("success"):
        logger = __import__("logging").getLogger(__name__)
        logger.debug("owner working context redis save missed; using process fallback")
    return ctx


__all__ = [
    "load_working_context",
    "format_working_context_block",
    "update_working_context_after_turn",
]

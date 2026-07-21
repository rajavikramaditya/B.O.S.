"""
Command Center interaction recorder — structured session + turn history for agent analysis.

Never stores unlock phrases, API keys, or raw secrets.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import database as db
from services.safety.admin_unlock import (
    SESSION_COOKIE_NAME,
    cookie_secure_flag,
    session_cookie_max_age,
    verify_session_token,
)

logger = logging.getLogger(__name__)

CC_SESSION_COOKIE = "neena_cc_session"
MAX_INPUT_LEN = 4000
MAX_REPLY_LEN = 12000
MAX_TRACE_JSON_LEN = 24000

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-z0-9]{10,}"),
)

_TRACE_SUMMARY_KEYS = (
    "source",
    "route",
    "route_type",
    "intent",
    "confidence",
    "operation_intent",
    "intent_confidence",
    "intent_source",
    "workflow_name",
    "policy_decision",
    "tool",
    "tool_suggested",
    "tool_executed",
    "executed_tool_name",
    "local_tool_executed",
    "protected_action_blocked",
    "protected_action_requested",
    "needs_owner_approval",
    "approval_blocked_reason",
    "selected_model",
    "actual_model",
    "actual_api_model_id",
    "fallback_used",
    "fallback_model_used",
    "model_call_status",
    "model_unavailable_reason",
    "model_rate_limited",
    "intent_model_call_count",
    "response_model_call_count",
    "total_model_call_count",
    "final_reply_source",
    "session_backend",
    "redis_available",
    "pending_state_source",
    "redis_fallback_reason",
    "whatsapp_gateway",
    "mode",
    "handled",
    "job_id",
    "ui_action",
    "approval_id",
    "capsule_id",
    "approval_status",
    "require_confirmation",
    # Customer WhatsApp (listener path only — never used on owner turns)
    "customer_phone_last10",
    "customer_phone_masked",
    "customer_sender_name",
    "customer_history_source",
    "customer_redis_write_ok",
    "station_situation",
    # Memory R/W audit
    "memory_mode",
    "memory_search_used",
    "memory_hits_count",
    "memory_save_status",
    "memory_write_backend",
    "memory_backend",
    "semantic_memory_used",
    "memory_fallback_reason",
    "pending_candidate_active",
    # Reachability / blinks
    "reached_interpreter",
    "reached_model",
    "short_circuit_reason",
    "pending_cleared_without_execute",
    "pending_action_snapshot",
    "action_packet_summary",
    "capsule_id_resolved",
    "azuracast_push_block_reason",
    "blink_events",
    # Mid-loop / agent step audit (clipped digests — never full packets)
    "agent_loop_steps",
    "factual_packet_digest",
    "event_kind",
    "media_kind",
    "media_file",
    "admin_event",
    "job_status",
)


def _admin_session_active(request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME) if request is not None else None
    return bool(token and verify_session_token(token))


def _clip(text: str | None, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def redact_sensitive_text(text: str | None) -> str:
    value = (text or "").strip()
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[redacted]", value)
    return value


def _digest_agent_loop_steps(result: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Build a clipped mid-loop step list for durable audit (no secrets / full packets)."""
    steps = result.get("agent_loop_steps")
    if not isinstance(steps, list) or not steps:
        fp = result.get("factual_packet")
        if isinstance(fp, dict) and fp.get("tool") == "agent_loop":
            steps = fp.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    out: list[dict[str, Any]] = []
    for s in steps[-16:]:
        if not isinstance(s, dict):
            continue
        out.append(
            {
                k: s.get(k)
                for k in ("n", "action", "action_type", "ok", "source", "decision", "reason")
                if s.get(k) is not None
            }
        )
    return out or None


def _factual_packet_digest(result: dict[str, Any]) -> str | None:
    if result.get("factual_packet_digest"):
        return _clip(str(result.get("factual_packet_digest")), 700)
    fp = result.get("factual_packet")
    if not isinstance(fp, dict):
        return None
    if fp.get("factual_digest"):
        return _clip(str(fp.get("factual_digest")), 700)
    if fp.get("tool") == "agent_loop":
        bits = []
        for s in (fp.get("steps") or [])[:8]:
            if isinstance(s, dict):
                bits.append(f"{s.get('action') or '?'}:{s.get('action_type') or ''}")
        return _clip(
            f"agent_loop step_count={fp.get('step_count')} steps=" + ",".join(bits),
            700,
        )
    tool = fp.get("tool") or fp.get("status") or ""
    if tool:
        return _clip(f"tool={tool}", 200)
    return None


def build_trace_summary(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {}
    summary: dict[str, Any] = {}
    for key in _TRACE_SUMMARY_KEYS:
        if key in result and result[key] is not None:
            summary[key] = result[key]
    # Prefer digest keys first so MAX_TRACE_JSON_LEN truncate keeps mid-loop audit
    loop_steps = _digest_agent_loop_steps(result)
    if loop_steps is not None:
        summary["agent_loop_steps"] = loop_steps
    digest = _factual_packet_digest(result)
    if digest:
        summary["factual_packet_digest"] = digest
    timing = result.get("timing")
    if isinstance(timing, dict):
        summary["timing"] = {
            k: timing.get(k)
            for k in ("total_ms", "llm_ms", "tools_ms", "db_ms")
            if timing.get(k) is not None
        }
    llm = result.get("llm")
    if isinstance(llm, dict):
        summary["llm"] = {
            k: llm.get(k)
            for k in ("used", "provider", "status")
            if llm.get(k) is not None
        }
    trace_steps = result.get("trace")
    if isinstance(trace_steps, list):
        summary["trace_steps"] = trace_steps[-8:]
    # Clip nested blink/packet payloads so SQLite stays bounded
    blinks = summary.get("blink_events")
    if isinstance(blinks, list) and len(blinks) > 24:
        summary["blink_events"] = blinks[-24:]
    pkt = summary.get("action_packet_summary")
    if isinstance(pkt, dict):
        summary["action_packet_summary"] = {
            k: pkt.get(k)
            for k in ("action", "confidence", "slots", "route", "source")
            if pkt.get(k) is not None
        }
    snap = summary.get("pending_action_snapshot")
    if isinstance(snap, dict):
        summary["pending_action_snapshot"] = {
            k: snap.get(k)
            for k in ("action_type", "protected", "resume_action", "capsule_id", "status")
            if snap.get(k) is not None
        }
    return summary


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in ("yes", "true", "1")


def resolve_turn_outcome(
    result: dict[str, Any] | None,
    *,
    outcome: str | None = None,
    blocked: bool = False,
) -> tuple[str, bool, str | None]:
    """Derive (outcome, blocked, block_reason) consistently for all record helpers."""
    result = result or {}
    blocked_flag = blocked or _truthy(result.get("protected_action_blocked")) or _truthy(
        result.get("blocked")
    )
    reason = (
        result.get("approval_blocked_reason")
        or result.get("block_reason")
        or result.get("azuracast_push_block_reason")
        or result.get("short_circuit_reason")
    )
    if isinstance(reason, str):
        reason = reason.strip() or None
    else:
        reason = None

    explicit = (outcome or result.get("outcome") or "").strip()
    if blocked_flag:
        return (explicit or "blocked"), True, reason
    if _truthy(result.get("require_confirmation")) or _truthy(result.get("needs_owner_approval")):
        return (explicit or "pending_confirm"), False, reason
    at = str(result.get("action_type") or "").upper()
    if "BLOCKED" in at:
        return (explicit or "blocked"), True, reason or at
    if "CONFIRM" in at:
        return (explicit or "pending_confirm"), False, reason
    if explicit:
        return explicit, False, reason
    if result.get("handled") is False:
        return "not_handled", False, reason
    if result.get("ok") is False or result.get("success") is False:
        return "error", False, reason
    return "success", False, reason


def _trace_json(result: dict[str, Any] | None) -> str | None:
    payload = build_trace_summary(result)
    if not payload:
        return None
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if len(raw) > MAX_TRACE_JSON_LEN:
        raw = raw[: MAX_TRACE_JSON_LEN - 3] + "..."
    return raw


def start_session() -> str:
    session_id = str(uuid.uuid4())
    db.start_command_center_session(session_id)
    return session_id


def end_session(session_id: str | None, end_reason: str = "lock") -> None:
    if not session_id:
        return
    try:
        db.end_command_center_session(session_id, end_reason=end_reason)
    except Exception as exc:
        logger.warning("command_center_recorder: end_session failed: %s", type(exc).__name__)


def resolve_session(request) -> tuple[str | None, bool]:
    """
    Return (session_id, is_new).
  If admin is unlocked but no open session cookie exists, create one.
    """
    if request is None:
        return None, False
    existing = (request.cookies.get(CC_SESSION_COOKIE) or "").strip()
    if existing and db.command_center_session_is_open(existing):
        return existing, False
    if not _admin_session_active(request):
        return None, False
    return start_session(), True


def apply_session_cookie(response, session_id: str) -> None:
    response.set_cookie(
        key=CC_SESSION_COOKIE,
        value=session_id,
        max_age=session_cookie_max_age(),
        httponly=True,
        secure=cookie_secure_flag(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(key=CC_SESSION_COOKIE, path="/")


def record_turn(
    *,
    session_id: str | None,
    channel: str,
    user_input: str,
    result: dict[str, Any] | None = None,
    selected_model: str | None = None,
    latency_ms: int | None = None,
    outcome: str | None = None,
    blocked: bool = False,
    block_reason: str | None = None,
) -> int | None:
    try:
        result = result or {}
        reply = redact_sensitive_text(result.get("reply") or result.get("owner_message"))
        resolved_outcome, blocked_flag, resolved_reason = resolve_turn_outcome(
            result, outcome=outcome, blocked=blocked
        )
        turn_id = db.insert_command_center_turn(
            session_id=session_id,
            channel=channel,
            user_input=_clip(redact_sensitive_text(user_input), MAX_INPUT_LEN),
            assistant_reply=_clip(reply, MAX_REPLY_LEN) or None,
            intent=(result.get("intent") or result.get("operation_intent")),
            route=result.get("route"),
            action_type=result.get("action_type") or result.get("ui_action") or result.get("admin_event"),
            policy_decision=result.get("policy_decision"),
            command_triggered=result.get("command_triggered"),
            outcome=resolved_outcome,
            blocked=blocked_flag,
            block_reason=block_reason or resolved_reason,
            selected_model=selected_model or result.get("selected_model"),
            actual_model=result.get("actual_model") or result.get("actual_api_model_id"),
            latency_ms=latency_ms,
            trace_json=_trace_json(result),
        )
        return turn_id
    except Exception as exc:
        logger.warning("command_center_recorder: record_turn failed: %s", type(exc).__name__)
        return None


def record_chat_turn(
    *,
    request,
    user_input: str,
    result: dict[str, Any],
    selected_model: str | None,
    latency_ms: int | None,
) -> tuple[int | None, str | None, bool]:
    session_id, is_new = resolve_session(request)
    turn_id = record_turn(
        session_id=session_id,
        channel="chat",
        user_input=user_input,
        result=result,
        selected_model=selected_model,
        latency_ms=latency_ms,
    )
    return turn_id, session_id, is_new


def resolve_whatsapp_session(tag: str = "owner") -> str:
    """Stable per-day WhatsApp session id so a day's WhatsApp chat groups together.

    WhatsApp has no cookie/session, so we key by UTC date. Idempotent: reuse an
    open session, else start one (duplicate starts are swallowed)."""
    from datetime import datetime, timezone

    sid = f"whatsapp-{tag}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        if not db.command_center_session_is_open(sid):
            db.start_command_center_session(sid)
    except Exception:
        pass
    return sid


def record_whatsapp_turn(
    *,
    user_input: str,
    result: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    is_owner: bool = True,
) -> int | None:
    """Record a real WhatsApp interaction (owner or listener) into the same
    interaction history used for agent analysis, with the full trace summary.

    Owner sessions stay `whatsapp-owner-YYYYMMDD` (unchanged).
    Customer sessions group by phone last-10: `whatsapp-customer-{last10}-YYYYMMDD`.
    """
    result = result or {}
    if is_owner:
        session_id = resolve_whatsapp_session("owner")
        channel = "whatsapp"
    else:
        last10 = str(result.get("customer_phone_last10") or "").strip()
        digits = "".join(c for c in last10 if c.isdigit())
        tag = f"customer-{digits[-10:]}" if len(digits) >= 4 else "listener"
        session_id = resolve_whatsapp_session(tag)
        channel = "whatsapp_listener"
        # Prefix input so agent/owner analysis can see who texted without opening trace.
        name = str(result.get("customer_sender_name") or "ji").strip() or "ji"
        masked = str(result.get("customer_phone_masked") or "").strip()
        label = f"[customer {name} {masked}] " if masked else f"[customer {name}] "
        if not (user_input or "").startswith("[customer "):
            user_input = label + (user_input or "")
    return record_turn(
        session_id=session_id,
        channel=channel,
        user_input=user_input,
        result=result,
        latency_ms=latency_ms,
    )


def record_live_ops_turn(
    *,
    request,
    user_input: str,
    action: str,
    result: dict[str, Any],
    latency_ms: int | None,
) -> tuple[int | None, str | None, bool]:
    session_id, is_new = resolve_session(request)
    channel = "live_ops_action" if (action or "").strip() else "live_ops_message"
    turn_id = record_turn(
        session_id=session_id,
        channel=channel,
        user_input=user_input or action or "",
        result=result,
        latency_ms=latency_ms,
        outcome="success" if result.get("handled") else "not_handled",
    )
    return turn_id, session_id, is_new


def _system_session(tag: str) -> str:
    """Stable per-day session for non-cookie channels (admin/cockpit/broadcast/probe)."""
    from datetime import datetime, timezone

    sid = f"{tag}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        if not db.command_center_session_is_open(sid):
            db.start_command_center_session(sid)
    except Exception:
        pass
    return sid


def record_cockpit_action_turn(
    *,
    request=None,
    action: str,
    result: dict[str, Any] | None = None,
    latency_ms: int | None = None,
) -> int | None:
    result = dict(result or {})
    result.setdefault("ui_action", action)
    result.setdefault("action_type", f"COCKPIT_{str(action or '').upper()}")
    result.setdefault("route", "cockpit_action")
    session_id, _ = resolve_session(request) if request is not None else (None, False)
    if not session_id:
        session_id = _system_session("cockpit")
    return record_turn(
        session_id=session_id,
        channel="cockpit_action",
        user_input=f"cockpit:{action}",
        result=result,
        latency_ms=latency_ms,
    )


def record_voice_turn(
    *,
    request=None,
    text: str,
    result: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    event_kind: str = "speak",
) -> int | None:
    result = dict(result or {})
    result.setdefault("event_kind", event_kind)
    result.setdefault("action_type", f"COCKPIT_VOICE_{event_kind.upper()}")
    result.setdefault("route", "cockpit_voice")
    result.setdefault("reply", result.get("status") or result.get("message") or event_kind)
    session_id, _ = resolve_session(request) if request is not None else (None, False)
    if not session_id:
        session_id = _system_session("voice")
    return record_turn(
        session_id=session_id,
        channel="cockpit_voice",
        user_input=_clip(text or f"voice:{event_kind}", 500),
        result=result,
        latency_ms=latency_ms,
    )


def record_broadcast_turn(
    *,
    action: str,
    capsule_id: int | None = None,
    result: dict[str, Any] | None = None,
    latency_ms: int | None = None,
) -> int | None:
    result = dict(result or {})
    result.setdefault("ui_action", action)
    result.setdefault("action_type", f"BROADCAST_{str(action or '').upper()}")
    result.setdefault("route", "broadcast_http")
    if capsule_id is not None:
        result.setdefault("capsule_id", capsule_id)
    if "reply" not in result:
        status = result.get("status") or ("ok" if result.get("success") else "done")
        result["reply"] = f"{action} capsule={capsule_id} status={status}"
    return record_turn(
        session_id=_system_session("broadcast"),
        channel="broadcast",
        user_input=f"broadcast:{action}" + (f"#{capsule_id}" if capsule_id is not None else ""),
        result=result,
        latency_ms=latency_ms,
    )


def record_admin_event(
    *,
    event: str,
    result: dict[str, Any] | None = None,
    session_id: str | None = None,
    blocked: bool = False,
    outcome: str | None = None,
) -> int | None:
    result = dict(result or {})
    result.setdefault("admin_event", event)
    result.setdefault("action_type", f"ADMIN_{str(event or '').upper()}")
    result.setdefault("route", "admin")
    result.setdefault("reply", result.get("detail") or event)
    sid = session_id or _system_session("admin")
    return record_turn(
        session_id=sid,
        channel="admin",
        user_input=f"admin:{event}",
        result=result,
        blocked=blocked,
        outcome=outcome,
    )


def record_probe_turn(
    *,
    user_input: str,
    result: dict[str, Any] | None = None,
    latency_ms: int | None = None,
) -> int | None:
    result = dict(result or {})
    result.setdefault("route", "probe_inprocess")
    result.setdefault("source", "neena_interaction_probe")
    return record_turn(
        session_id=_system_session("probe"),
        channel="probe",
        user_input=user_input,
        result=result,
        latency_ms=latency_ms,
    )


def record_job_completion_turns(jobs: list[dict[str, Any]] | None) -> list[int]:
    """Record drained pending-completions so background work is not invisible."""
    ids: list[int] = []
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("job_id") or "").strip()
        status = str(job.get("status") or "").strip() or "unknown"
        action = str(job.get("action") or "").strip() or "job"
        result = {
            "reply": job.get("owner_message") or job.get("error_summary") or status,
            "job_id": job_id,
            "job_status": status,
            "ui_action": action,
            "action_type": f"JOB_{status.upper()}",
            "route": "job_completion",
            "ok": status == "succeeded",
            "success": status == "succeeded",
        }
        if status == "failed":
            result["block_reason"] = job.get("error_summary")
        turn_id = record_turn(
            session_id=_system_session("jobs"),
            channel="job_completion",
            user_input=f"job:{action}:{job_id}",
            result=result,
            outcome="success" if status == "succeeded" else "error",
        )
        if turn_id is not None:
            ids.append(turn_id)
    return ids


def _channel_exact_match(row_channel: str, wanted: str) -> bool:
    """Exact channel match — 'whatsapp' must NOT match 'whatsapp_listener'."""
    return (row_channel or "").strip() == (wanted or "").strip()


def build_recent_interaction_bundle(
    *,
    session_limit: int = 10,
    turn_limit: int = 40,
    channel: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    sessions = db.list_command_center_sessions(limit=session_limit)
    # Over-fetch when filtering so recent_turns still fills turn_limit
    fetch_limit = turn_limit * 4 if channel or session_id else turn_limit
    turns = db.list_command_center_turns(session_id=session_id, limit=fetch_limit)
    if channel:
        turns = [t for t in turns if _channel_exact_match(str(t.get("channel") or ""), channel)]
    turns = turns[:turn_limit]
    for turn in turns:
        raw = turn.pop("trace_json", None)
        if raw:
            try:
                turn["trace"] = json.loads(raw)
            except json.JSONDecodeError:
                turn["trace"] = {"parse_error": True}
    by_session: dict[str, list[dict[str, Any]]] = {}
    for turn in turns:
        sid = turn.get("session_id") or "_unscoped"
        by_session.setdefault(sid, []).append(turn)
    return {
        "status": "success",
        "sessions": sessions,
        "recent_turns": turns,
        "turns_by_session": by_session,
        "channel_filter": channel,
        "session_filter": session_id,
        "note": "Read-only interaction history for agent analysis. No unlock phrases or secrets stored.",
    }


__all__ = [
    "CC_SESSION_COOKIE",
    "apply_session_cookie",
    "build_recent_interaction_bundle",
    "build_trace_summary",
    "clear_session_cookie",
    "end_session",
    "record_admin_event",
    "record_broadcast_turn",
    "record_chat_turn",
    "record_cockpit_action_turn",
    "record_job_completion_turns",
    "record_live_ops_turn",
    "record_probe_turn",
    "record_turn",
    "record_voice_turn",
    "record_whatsapp_turn",
    "redact_sensitive_text",
    "resolve_session",
    "resolve_turn_outcome",
    "resolve_whatsapp_session",
    "start_session",
]

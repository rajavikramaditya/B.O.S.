"""Future intentions — durable plans (“kal X karna hai”), facts only.

Save/recall/lifecycle return factual_packet + short fallback_line.
Owner Hinglish is composed by maybe_humanize_report — never canned Sir-templates here.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TYPE_FUTURE_INTENTION = "neena_future_intention"
IST = timezone(timedelta(hours=5, minutes=30))
STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

# Statement: owner is recording a plan / intention (autosave).
_FUTURE_SAVE_RE = re.compile(
    r"(?:"
    r"\b(?:kal|parso|aaj|agle|agli|next|is\s+hafte?|tomorrow)\b.{0,90}"
    r"\b(?:karna\s+hai|karna\s+padega|karenge|karega|karegi|plan\s+hai|yaad\s+rakh)|"
    r"\b(?:mera\s+plan|plan\s+hai|intention|todo)\b|"
    r"\b(?:kal|parso|tomorrow)\b.{0,50}\b(?:karna|karenge|karega)\b"
    r")",
    re.I | re.S,
)

# Question: owner asking what is planned.
_FUTURE_ASK_RE = re.compile(
    r"(?:"
    r"\b(?:kya\s+plan|kya\s+karna\s+hai|mere\s+plan|plans?\b|intention|todo|"
    r"kal\s+kya\s+kar|parso\s+kya\s+kar|aage\s+kya|"
    r"what(?:'s|\s+is)\s+(?:the\s+)?plan|"
    r"what\s+(?:do\s+we|should\s+we)\s+do)\b"
    r")",
    re.I,
)

# Lifecycle — compound markers only (never bare haan / ho gaya).
_COMPLETE_RE = re.compile(
    r"(?:"
    r"\bplan\s+ho\s+gaya\b|"
    r"\bintention\s+complete\b|"
    r"\bye\s+plan\s+done\b|"
    r"\bplan\s+done\b|"
    r"\bid\s*[:=]?\s*\d+\s+complete\b|"
    r"\bcomplete\s+(?:plan|intention)\b|"
    r"\bplan\s+complete\b"
    r")",
    re.I,
)
_CANCEL_RE = re.compile(
    r"(?:"
    r"\bplan\s+cancel\b|"
    r"\bintention\s+cancel\b|"
    r"\bwoh\s+plan\s+rehne\s+do\b|"
    r"\bplan\s+rehne\s+do\b|"
    r"\bcancel\s+(?:plan|intention)\b|"
    r"\bid\s*[:=]?\s*\d+\s+cancel\b"
    r")",
    re.I,
)
_POSTPONE_RE = re.compile(
    r"(?:"
    r"\bplan\s+postpone\b|"
    r"\bpostpone\s+(?:plan|intention|to)\b|"
    r"\bplan\s+kal\s+shift\b|"
    r"\bshift\s+plan\b|"
    r"\bplan\s+shift\b"
    r")",
    re.I,
)

_PAST_ASK_RE = re.compile(
    r"\b(?:kya\s+hua|kya\s+huya|kya\s+kiya|discuss|diary|pehle\s+kya|what\s+happened)\b",
    re.I,
)

_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ID_RE = re.compile(r"\bid\s*[:=]?\s*(\d+)\b", re.I)
_THREAD_KEY_RE = re.compile(r"\bthread\s*[:=]\s*([a-z0-9_\-]{2,40})\b", re.I)


def _now_ist(now: datetime | None = None) -> datetime:
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(IST)


def extract_thread_key(message: str) -> str | None:
    m = _THREAD_KEY_RE.search(message or "")
    if not m:
        return None
    return m.group(1).strip().lower()


def is_future_intention_statement(message: str) -> bool:
    """Deprecated router — always False. future_intention_save is catalog tool."""
    del message
    return False


def is_future_intention_question(message: str) -> bool:
    """Deprecated router — always False. future_intention_recall is catalog tool."""
    del message
    return False


def detect_lifecycle_op(message: str) -> str | None:
    """Return complete|cancel|postpone or None. Compound markers only."""
    msg = (message or "").strip()
    if not msg:
        return None
    if _COMPLETE_RE.search(msg):
        return "complete"
    if _CANCEL_RE.search(msg):
        return "cancel"
    if _POSTPONE_RE.search(msg):
        return "postpone"
    return None


def is_future_intention_lifecycle(message: str) -> bool:
    return detect_lifecycle_op(message) is not None


def resolve_intention_target_date(message: str, *, now: datetime | None = None) -> str | None:
    """Optional target date IST for the plan (metadata), allowlisted anchors only."""
    msg = (message or "").strip()
    now_ist = _now_ist(now)
    today = now_ist.date()
    lower = msg.lower()

    iso = _ISO_DATE_RE.search(msg)
    if iso:
        try:
            return date.fromisoformat(iso.group(1)).isoformat()
        except ValueError:
            return None

    if re.search(r"\b(this\s+week|is\s+hafte|is\s+hafta)\b", lower):
        return today.isoformat()
    if re.search(r"\bparso\b", lower):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"\b(kal|tomorrow)\b", lower):
        return (today + timedelta(days=1)).isoformat()
    if re.search(r"\b(aaj|today)\b", lower):
        return today.isoformat()
    return None


def extract_intention_content(message: str) -> str:
    text = (message or "").strip()
    if not text:
        return ""
    cleaned = re.sub(
        r"(?i)\b(yaad\s+rakh(?:na|o|lo)?(?:\s+hai)?|remember\s+this|plan\s+hai\s+ki|mera\s+plan\s+hai|"
        r"thread\s*[:=]\s*[a-z0-9_\-]{2,40})\b[:\s,-]*",
        "",
        text,
    ).strip(" \t\r\n,.:;-\"'")
    return cleaned or text


def _row_status(meta: dict) -> str:
    s = (meta.get("status") or STATUS_OPEN).strip().lower()
    if s not in (STATUS_OPEN, STATUS_DONE, STATUS_CANCELLED):
        return STATUS_OPEN
    return s


def list_active_intentions(
    *,
    limit: int = 20,
    target_date_ist: str | None = None,
    status: str = STATUS_OPEN,
    thread_key: str | None = None,
) -> list[dict[str, Any]]:
    try:
        from services.memory.pg_repository import list_active_memories_pg

        rows = list_active_memories_pg(
            limit=max(limit * 3, 60),
            memory_type=TYPE_FUTURE_INTENTION,
            actor_role="owner",
            subject_key="owner",
        ).get("memories") or []
    except Exception as exc:
        logger.debug("list_active_intentions skip: %s", type(exc).__name__)
        return []

    out: list[dict[str, Any]] = []
    want_status = (status or STATUS_OPEN).strip().lower()
    want_thread = (thread_key or "").strip().lower() or None
    for r in rows:
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        st = _row_status(meta)
        if want_status != "any" and st != want_status:
            continue
        td = (meta.get("target_date_ist") or "").strip() or None
        if target_date_ist and td and td != target_date_ist:
            continue
        tk = (meta.get("thread_key") or "").strip().lower() or None
        if want_thread and tk != want_thread:
            continue
        out.append(
            {
                "id": r.get("id"),
                "content": (r.get("content") or "").strip(),
                "target_date_ist": td,
                "status": st,
                "thread_key": tk,
                "memory_type": TYPE_FUTURE_INTENTION,
            }
        )
        if len(out) >= limit:
            break
    return out


def _resolve_target_intention(message: str) -> dict[str, Any] | None:
    """Stable id= first, else latest open intention."""
    from services.memory.pg_repository import get_memory_pg

    mid = None
    m = _ID_RE.search(message or "")
    if m:
        mid = int(m.group(1))
    if mid is not None:
        row = (get_memory_pg(mid) or {}).get("memory")
        if row and (row.get("memory_type") or "") == TYPE_FUTURE_INTENTION:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            return {
                "id": row.get("id"),
                "content": (row.get("content") or "").strip(),
                "target_date_ist": (meta.get("target_date_ist") or None),
                "status": _row_status(meta),
                "thread_key": (meta.get("thread_key") or None),
                "metadata": meta,
            }
        return None
    open_items = list_active_intentions(limit=1, status=STATUS_OPEN)
    return open_items[0] if open_items else None


def _patch_intention_meta(memory_id: int, patch: dict[str, Any]) -> bool:
    from services.memory.pg_repository import update_memory_metadata_pg

    res = update_memory_metadata_pg(int(memory_id), patch)
    return bool(res.get("success"))


def apply_lifecycle(
    message: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """complete / cancel / postpone an intention. Facts only."""
    op = detect_lifecycle_op(message)
    if not op:
        return {
            "ok": False,
            "factual_packet": {
                "tool": "future_intention_lifecycle",
                "status": "not_lifecycle",
            },
            "fallback_line": "Not a future-intention lifecycle command.",
            "action_type": "FUTURE_INTENTION_RECALL",
        }

    target = _resolve_target_intention(message)
    if not target:
        packet = {
            "tool": "future_intention_lifecycle",
            "operation": op,
            "status": "not_found",
            "applied": False,
        }
        return {
            "ok": False,
            "factual_packet": packet,
            "fallback_line": f"Future intention {op} failed: no matching open intention (use id=N).",
            "action_type": (
                "FUTURE_INTENTION_COMPLETE"
                if op == "complete"
                else "FUTURE_INTENTION_CANCEL"
                if op == "cancel"
                else "FUTURE_INTENTION_POSTPONE"
            ),
        }

    mid = int(target["id"])
    now_ist = _now_ist(now)
    if op == "complete":
        ok = _patch_intention_meta(
            mid,
            {"status": STATUS_DONE, "completed_at": now_ist.isoformat()},
        )
        action = "FUTURE_INTENTION_COMPLETE"
        status_label = STATUS_DONE
        extra: dict[str, Any] = {"completed_at": now_ist.isoformat()}
    elif op == "cancel":
        ok = _patch_intention_meta(
            mid,
            {"status": STATUS_CANCELLED, "completed_at": now_ist.isoformat()},
        )
        action = "FUTURE_INTENTION_CANCEL"
        status_label = STATUS_CANCELLED
        extra = {"completed_at": now_ist.isoformat()}
    else:
        new_date = resolve_intention_target_date(message, now=now)
        if not new_date:
            packet = {
                "tool": "future_intention_lifecycle",
                "operation": "postpone",
                "status": "needs_date",
                "memory_id": mid,
                "applied": False,
            }
            return {
                "ok": False,
                "factual_packet": packet,
                "fallback_line": (
                    f"Future intention postpone needs target date "
                    f"(kal/parso/YYYY-MM-DD). id={mid}."
                ),
                "action_type": "FUTURE_INTENTION_POSTPONE",
            }
        ok = _patch_intention_meta(
            mid,
            {"status": STATUS_OPEN, "target_date_ist": new_date, "postponed_at": now_ist.isoformat()},
        )
        action = "FUTURE_INTENTION_POSTPONE"
        status_label = STATUS_OPEN
        extra = {"target_date_ist": new_date}

    packet = {
        "tool": "future_intention_lifecycle",
        "operation": op,
        "status": "ok" if ok else "failed",
        "applied": ok,
        "memory_id": mid,
        "intention_status": status_label,
        "content": (target.get("content") or "")[:160],
        **extra,
    }
    fallback = (
        f"Future intention {op}. applied={ok} id={mid} "
        f"status={status_label} content={(target.get('content') or '')[:120]}"
    )
    return {
        "ok": ok,
        "factual_packet": packet,
        "fallback_line": fallback,
        "action_type": action,
    }


def save_future_intention(
    message: str,
    *,
    now: datetime | None = None,
    with_embeddings: bool = False,
) -> dict[str, Any]:
    """Persist one intention from an owner statement. Facts only."""
    from services.memory.contract import classify_memory_candidate, make_memory_write_decision_from_candidate
    from services.memory.service import _persist_confirmed_permanent_candidate

    content = extract_intention_content(message)
    if not content:
        packet = {
            "tool": "future_intention_save",
            "status": "needs_content",
            "saved": False,
        }
        return {
            "ok": False,
            "factual_packet": packet,
            "fallback_line": "Future intention needs one clear plan line.",
            "action_type": "FUTURE_INTENTION_NEEDS_CONTENT",
        }

    target = resolve_intention_target_date(message, now=now)
    thread_key = extract_thread_key(message)
    meta = {
        "stage": "future_intention_autosave",
        "section": "future",
        "target_date_ist": target,
        "status": STATUS_OPEN,
        "title": "Future intention",
    }
    if thread_key:
        meta["thread_key"] = thread_key

    candidate = classify_memory_candidate(
        content=content,
        memory_type=TYPE_FUTURE_INTENTION,
        source_message=message,
        owner_confirmed=True,
        retention="permanent",
        sensitivity_level="normal",
        metadata=meta,
    )
    if with_embeddings:
        candidate.setdefault("metadata", {})["embedding"] = "requested"
    else:
        candidate.setdefault("metadata", {})["embedding"] = "disabled"

    decision = make_memory_write_decision_from_candidate(candidate)
    if candidate.get("blocked_reason") and candidate.get("blocked_reason") != "owner_confirmation_required":
        return {
            "ok": False,
            "factual_packet": {
                "tool": "future_intention_save",
                "status": "blocked",
                "saved": False,
                "reason": candidate.get("reason"),
            },
            "fallback_line": f"Future intention blocked: {candidate.get('reason')}",
            "action_type": "FUTURE_INTENTION_BLOCKED",
            "decision": decision,
        }

    persisted = _persist_confirmed_permanent_candidate(
        candidate,
        message,
        soft_ack=True,
        event_type="created_from_future_intention",
    )
    packet = {
        "tool": "future_intention_save",
        "status": "saved" if persisted.get("ok") else "failed",
        "saved": bool(persisted.get("ok")),
        "content": content,
        "target_date_ist": target,
        "status_value": STATUS_OPEN,
        "thread_key": thread_key,
        "memory_id": persisted.get("postgres_memory_id") or persisted.get("sqlite_memory_id"),
    }
    fallback = (
        f"Future intention saved. target_date_ist={target or 'unspecified'} "
        f"thread_key={thread_key or '-'} content={content[:160]}"
    )
    return {
        "ok": bool(persisted.get("ok")),
        "factual_packet": packet,
        "fallback_line": fallback,
        "action_type": "FUTURE_INTENTION_SAVED",
        "persist": persisted,
    }


def build_future_recall_packet(
    message: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    target = resolve_intention_target_date(message, now=now)
    thread_key = extract_thread_key(message)
    items = list_active_intentions(
        limit=15,
        target_date_ist=None,
        status=STATUS_OPEN,
        thread_key=thread_key,
    )
    filtered = [i for i in items if not target or i.get("target_date_ist") == target] if target else items
    if target and not filtered and not thread_key:
        filtered = items

    siblings = []
    if thread_key:
        siblings = [
            i for i in list_active_intentions(limit=15, status=STATUS_OPEN, thread_key=thread_key)
            if i.get("id") not in {x.get("id") for x in filtered}
        ]

    packet: dict[str, Any] = {
        "tool": "future_intention_recall",
        "status": "ok",
        "timezone": "Asia/Kolkata",
        "target_date_ist": target,
        "thread_key": thread_key,
        "count": len(filtered),
        "intentions": filtered,
        "thread_siblings": siblings,
    }
    if not filtered:
        fallback = (
            f"Future intentions empty. target_date_ist={target or 'any'} "
            f"thread_key={thread_key or '-'} count=0."
        )
    else:
        lines = [
            f"id={i.get('id')} status={i.get('status')} target={i.get('target_date_ist') or '-'} "
            f"thread={i.get('thread_key') or '-'} {(i.get('content') or '')[:120]}"
            for i in filtered
        ]
        fallback = (
            f"Future intentions. target_date_ist={target or 'any'} "
            f"thread_key={thread_key or '-'} count={len(filtered)}.\n"
            + "\n".join(lines)
        )
    return {
        "factual_packet": packet,
        "fallback_line": fallback,
        "action_type": "FUTURE_INTENTION_RECALL",
    }


__all__ = [
    "TYPE_FUTURE_INTENTION",
    "STATUS_OPEN",
    "STATUS_DONE",
    "STATUS_CANCELLED",
    "is_future_intention_statement",
    "is_future_intention_question",
    "is_future_intention_lifecycle",
    "detect_lifecycle_op",
    "resolve_intention_target_date",
    "extract_intention_content",
    "extract_thread_key",
    "list_active_intentions",
    "save_future_intention",
    "apply_lifecycle",
    "build_future_recall_packet",
]

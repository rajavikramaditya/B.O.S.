"""Day memory — IST calendar windows + owner-day / week diary (facts only).

Reply path: return factual_packet + short factual fallback_line.
Owner Hinglish is composed by maybe_humanize_report — never canned Sir-templates here.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TYPE_DAY_SUMMARY = "neena_day_summary"
TYPE_WEEK_SUMMARY = "neena_week_summary"
# Fixed IST offset (repo already uses UTC+5:30 elsewhere; avoids ZoneInfo/tzdata on Windows).
IST = timezone(timedelta(hours=5, minutes=30))

# Owner / CC channels only — never listener customer turns.
OWNER_DAY_CHANNELS = (
    "chat",
    "whatsapp",
    "live_ops_message",
    "live_ops_action",
    "cockpit_action",
    "cockpit_voice",
    "broadcast",
    "admin",
    "job_completion",
)

# Allowlisted day/timeline anchors (same family as conversation-recall markers).
_DAY_ASK_RE = re.compile(
    r"(?:"
    r"\b(aaj|kal|parso|yesterday|today|this\s+week|is\s+hafte|is\s+hafta|"
    r"pichhle?\s+din|last\s+day|"
    r"pichhle?\s+(?:som(?:vaar)?|mangal(?:vaar)?|budh(?:vaar)?|guru(?:vaar)?|"
    r"shukr(?:vaar)?|shan(?:i|ivar)?|rav(?:i|ivar)?|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday))\b|"
    r"\b\d+\s*din\s*(?:pehle|pahle|ago)\b|"
    r"\b\d{4}-\d{2}-\d{2}\b"
    r")",
    re.I,
)
_DAY_INTENT_RE = re.compile(
    r"(?:"
    r"\bkya\s+(hua|huya|kiya|discuss|baat)|"
    r"\b(discuss|conversation|timeline|diary|summary|yaad)|"
    r"\bwhat\s+happened|"
    r"\bkya\s+hua|"
    r"\bkya\s+kar\s*rahe|"
    r"\bpehle\s+kya|"
    r"\bdin\s+(me|mein)\b"
    r")",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_N_DIN_PEHLE_RE = re.compile(r"\b(\d+)\s*din\s*(?:pehle|pahle|ago)\b", re.I)
_FUTURE_TENSE_RE = re.compile(
    r"\b(?:karna\s+hai|karenge|karega|karegi|plan|hoga|hogi|intention|todo)\b",
    re.I,
)
_PAST_TENSE_RE = re.compile(
    r"\b(?:hua|huya|kiya|discuss|baat|pehle|diary|happened|timeline)\b",
    re.I,
)

# Hindi weekday → Python weekday (Mon=0)
_WEEKDAY_NAMES = {
    "som": 0,
    "somvaar": 0,
    "monday": 0,
    "mangal": 1,
    "mangalvaar": 1,
    "tuesday": 1,
    "budh": 2,
    "budhvaar": 2,
    "wednesday": 2,
    "guru": 3,
    "guruvaar": 3,
    "thursday": 3,
    "shukr": 4,
    "shukrvaar": 4,
    "friday": 4,
    "shan": 5,
    "shani": 5,
    "shanivar": 5,
    "saturday": 5,
    "rav": 6,
    "ravi": 6,
    "ravivar": 6,
    "sunday": 6,
}
_WEEKDAY_ASK_RE = re.compile(
    r"\bpichhle?\s+(som(?:vaar)?|mangal(?:vaar)?|budh(?:vaar)?|guru(?:vaar)?|"
    r"shukr(?:vaar)?|shan(?:i|ivar)?|rav(?:i|ivar)?|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now_ist(now: datetime | None = None) -> datetime:
    base = now or _utcnow()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(IST)


def _day_bounds_ist(d: date) -> tuple[datetime, datetime]:
    start_ist = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    return start_ist.astimezone(timezone.utc), end_ist.astimezone(timezone.utc)


def _previous_weekday(today: date, weekday: int) -> date:
    """Most recent past occurrence of weekday (Mon=0), not today if today matches."""
    delta = (today.weekday() - weekday) % 7
    if delta == 0:
        delta = 7
    return today - timedelta(days=delta)


def is_day_memory_question(message: str) -> bool:
    """Deprecated router — always False. day_memory_recall is interpreter→catalog."""
    del message
    return False


def resolve_day_window(message: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Map allowlisted anchors → IST day or week window."""
    msg = (message or "").strip()
    now_ist = _now_ist(now)
    today = now_ist.date()
    lower = msg.lower()

    iso = _ISO_DATE_RE.search(msg)
    if iso:
        try:
            d = date.fromisoformat(iso.group(1))
        except ValueError:
            return {
                "ok": False,
                "status": "needs_clarification",
                "reason": "invalid_iso_date",
            }
        start_utc, end_utc = _day_bounds_ist(d)
        return {
            "ok": True,
            "kind": "day",
            "label": d.isoformat(),
            "date_ist": d.isoformat(),
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
        }

    n_pehle = _N_DIN_PEHLE_RE.search(msg)
    if n_pehle:
        n = int(n_pehle.group(1))
        if n < 1 or n > 60:
            return {
                "ok": False,
                "status": "needs_clarification",
                "reason": "day_offset_out_of_range",
            }
        d = today - timedelta(days=n)
        start_utc, end_utc = _day_bounds_ist(d)
        return {
            "ok": True,
            "kind": "day",
            "label": f"{n}_days_ago",
            "date_ist": d.isoformat(),
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
        }

    wd = _WEEKDAY_ASK_RE.search(msg)
    if wd:
        name = wd.group(1).lower()
        # normalize shanivar / ravi variants
        key = name
        for alias in _WEEKDAY_NAMES:
            if name.startswith(alias) or alias.startswith(name):
                key = alias
                break
        weekday = _WEEKDAY_NAMES.get(key)
        if weekday is None:
            # try without suffix
            for alias, val in _WEEKDAY_NAMES.items():
                if name.startswith(alias[:4]):
                    weekday = val
                    break
        if weekday is None:
            return {
                "ok": False,
                "status": "needs_clarification",
                "reason": "weekday_unclear",
            }
        d = _previous_weekday(today, weekday)
        start_utc, end_utc = _day_bounds_ist(d)
        return {
            "ok": True,
            "kind": "day",
            "label": f"last_{name}",
            "date_ist": d.isoformat(),
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
        }

    if re.search(r"\b(this\s+week|is\s+hafte|is\s+hafta)\b", lower):
        # Monday start (ISO weekday Mon=0)
        week_start = today - timedelta(days=today.weekday())
        start_utc, _ = _day_bounds_ist(week_start)
        _, end_utc = _day_bounds_ist(today)
        return {
            "ok": True,
            "kind": "week",
            "label": "this_week",
            "date_ist": None,
            "week_start_ist": week_start.isoformat(),
            "week_end_ist": today.isoformat(),
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
        }

    if re.search(r"\b(pichhle?\s+din|last\s+day)\b", lower):
        d = today - timedelta(days=1)
    elif re.search(r"\bparso\b", lower):
        # Past default; future tense alone is routed elsewhere.
        if _FUTURE_TENSE_RE.search(msg) and not _PAST_TENSE_RE.search(msg):
            d = today + timedelta(days=2)
        else:
            d = today - timedelta(days=2)
    elif re.search(r"\b(kal|yesterday|tomorrow)\b", lower):
        if "tomorrow" in lower or (
            re.search(r"\bkal\b", lower)
            and _FUTURE_TENSE_RE.search(msg)
            and not _PAST_TENSE_RE.search(msg)
        ):
            d = today + timedelta(days=1)
        elif "yesterday" in lower or re.search(r"\bkal\b", lower):
            d = today - timedelta(days=1)
        else:
            d = today - timedelta(days=1)
    elif re.search(r"\b(aaj|today)\b", lower):
        d = today
    else:
        return {
            "ok": False,
            "status": "needs_clarification",
            "reason": "day_anchor_unclear",
        }

    start_utc, end_utc = _day_bounds_ist(d)
    label = "today" if d == today else ("yesterday" if d == today - timedelta(days=1) else d.isoformat())
    if d == today - timedelta(days=2):
        label = "day_before_yesterday"
    if d == today + timedelta(days=1):
        label = "tomorrow"
    if d == today + timedelta(days=2):
        label = "day_after_tomorrow"
    return {
        "ok": True,
        "kind": "day",
        "label": label,
        "date_ist": d.isoformat(),
        "start_utc": start_utc.isoformat(),
        "end_utc": end_utc.isoformat(),
    }


def _truncate(text: str, n: int = 160) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= n:
        return t
    return t[: n - 3] + "..."


def list_owner_turns_for_window(
    start_utc: str,
    end_utc: str,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    import database as db

    rows = db.list_command_center_turns_between(
        start_utc,
        end_utc,
        limit=limit,
        channels=list(OWNER_DAY_CHANNELS),
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r.get("id"),
                "created_at": r.get("created_at"),
                "channel": r.get("channel"),
                "user": _truncate(r.get("user_input") or "", 140),
                "assistant": _truncate(r.get("assistant_reply") or "", 140),
                "action_type": r.get("action_type"),
                "route": r.get("route"),
                "outcome": r.get("outcome"),
                "blocked": bool(r.get("blocked")),
            }
        )
    return out


def _factual_timeline(turns: list[dict[str, Any]]) -> str:
    lines = []
    for t in turns:
        lines.append(
            f"[{t.get('created_at')}] ({t.get('channel')}) "
            f"user={t.get('user') or '-'} | action={t.get('action_type') or '-'} | "
            f"outcome={t.get('outcome') or '-'}"
        )
    return "\n".join(lines)


def _diary_digest(turns: list[dict[str, Any]], *, max_bits: int = 12) -> str:
    """Deterministic compress of turn facts — not owner speech, not LLM invent."""
    bits: list[str] = []
    for t in turns[:max_bits]:
        u = (t.get("user") or "").strip() or "-"
        a = (t.get("action_type") or "").strip() or "chat"
        o = (t.get("outcome") or "").strip() or "-"
        bits.append(f"{_truncate(u, 60)}→{a}:{o}")
    return "; ".join(bits)


def warm_compress_day_summary(
    date_ist: str,
    *,
    digest: str,
    timeline: str,
    turn_count: int,
    memory_id: int | None = None,
) -> dict[str, Any]:
    """Optional warm paragraph from cold facts only. Fail-closed if LLM unavailable."""
    from services.memory.pg_repository import update_memory_content_pg, update_memory_metadata_pg

    facts = (
        f"tool=day_diary_warm date_ist={date_ist} turn_count={turn_count}\n"
        f"Digest: {digest}\n"
        f"Timeline:\n{_truncate(timeline, 1200)}"
    )
    warm = None
    try:
        from services.brain.conversation import humanize_factual_reply

        warm = humanize_factual_reply(
            facts,
            f"Write one short diary paragraph for {date_ist} using only these facts.",
            concise=False,
        )
    except Exception as exc:
        logger.debug("warm_compress skip: %s", type(exc).__name__)
        warm = None

    if not (warm or "").strip():
        return {"success": False, "reason": "warm_unavailable", "date_ist": date_ist}

    warm_line = _truncate(warm.strip().replace("\n", " "), 600)
    # Rebuild stored content keeping cold truth first.
    content = (
        f"Day diary {date_ist} IST. turn_count={turn_count}.\n"
        f"Digest: {digest}\n"
        f"Warm: {warm_line}\n"
        f"Timeline:\n{timeline}"
    )
    if len(content) > 3500:
        content = content[:3497] + "..."

    if memory_id:
        try:
            update_memory_content_pg(int(memory_id), content)
            update_memory_metadata_pg(
                int(memory_id),
                {"warm": True, "warm_preview": warm_line[:240]},
            )
        except Exception as exc:
            logger.debug("warm persist skip: %s", type(exc).__name__)
            return {"success": False, "reason": "warm_persist_failed", "date_ist": date_ist}

    return {
        "success": True,
        "date_ist": date_ist,
        "warm": warm_line,
        "memory_id": memory_id,
    }


def get_day_summary_row(date_ist: str) -> dict[str, Any] | None:
    try:
        from services.memory.pg_repository import find_memory_pg_by_dedupe_key

        found = find_memory_pg_by_dedupe_key(f"neena_day_{date_ist}") or {}
        mem = found.get("memory")
        return mem if isinstance(mem, dict) and mem.get("id") else None
    except Exception as exc:
        logger.debug("get_day_summary_row skip: %s", type(exc).__name__)
        return None


def get_week_summary_row(week_start_ist: str, week_end_ist: str) -> dict[str, Any] | None:
    try:
        from services.memory.pg_repository import find_memory_pg_by_dedupe_key

        key = f"neena_week_{week_start_ist}_{week_end_ist}"
        found = find_memory_pg_by_dedupe_key(key) or {}
        mem = found.get("memory")
        return mem if isinstance(mem, dict) and mem.get("id") else None
    except Exception as exc:
        logger.debug("get_week_summary_row skip: %s", type(exc).__name__)
        return None


def upsert_day_summary(
    date_ist: str,
    *,
    with_embeddings: bool = False,
) -> dict[str, Any]:
    """Build/refresh factual day diary from turns. No polished owner speech."""
    from services.memory.pg_repository import (
        create_memory_pg_idempotent,
        is_postgres_available,
        update_memory_content_pg,
        update_memory_metadata_pg,
    )

    d = (date_ist or "").strip()
    if not d:
        return {"success": False, "reason": "missing_date"}

    try:
        day = date.fromisoformat(d)
    except ValueError:
        return {"success": False, "reason": "invalid_date"}

    start_utc, end_utc = _day_bounds_ist(day)
    turns = list_owner_turns_for_window(start_utc.isoformat(), end_utc.isoformat(), limit=60)
    if not turns:
        return {
            "success": False,
            "reason": "no_turns",
            "date_ist": d,
            "turn_count": 0,
        }

    digest = _diary_digest(turns)
    timeline = _factual_timeline(turns)
    content = (
        f"Day diary {d} IST. turn_count={len(turns)}.\n"
        f"Digest: {digest}\n"
        f"Timeline:\n{timeline}"
    )
    if len(content) > 3500:
        content = content[:3497] + "..."

    pg = is_postgres_available() or {}
    if not pg.get("available"):
        return {"success": False, "reason": pg.get("reason") or "postgres_unavailable", "date_ist": d}

    vector = None
    embed_model = None
    if with_embeddings:
        try:
            from services.memory.embedding_provider import embed_text

            emb = embed_text(content) or {}
            vector = emb.get("vector")
            embed_model = emb.get("model")
            if vector and len(vector) != 3072:
                vector = None
        except Exception:
            vector = None

    meta = {
        "section": "day",
        "date_ist": d,
        "turn_count": len(turns),
        "digest": digest[:500],
        "title": f"Day {d}",
    }

    try:
        res = create_memory_pg_idempotent(
            write_dedupe_key=f"neena_day_{d}",
            memory_type=TYPE_DAY_SUMMARY,
            content=content,
            owner_confirmed=True,
            importance=3,
            source="system_day_diary",
            retention="permanent",
            sensitivity_level="normal",
            metadata=meta,
            embedding_model=embed_model if vector else None,
            embedding_vector=vector,
            actor_role="owner",
            subject_key="owner",
            salience=0.75,
        )
    except Exception as exc:
        logger.warning("upsert_day_summary failed: %s", type(exc).__name__)
        return {"success": False, "reason": type(exc).__name__, "date_ist": d}

    if not res.get("success"):
        return {"success": False, "reason": res.get("reason") or "write_failed", "date_ist": d}

    refreshed = False
    if res.get("deduped"):
        mid = (res.get("memory") or {}).get("id")
        old = (res.get("memory") or {}).get("content") or ""
        if mid and old != content:
            try:
                update_memory_content_pg(int(mid), content)
                update_memory_metadata_pg(int(mid), meta)
                refreshed = True
            except Exception as exc:
                logger.debug("day diary refresh skip: %s", type(exc).__name__)

    mid = (res.get("memory") or {}).get("id")
    warm_out = None
    if len(turns) >= 3:
        warm_out = warm_compress_day_summary(
            d,
            digest=digest,
            timeline=timeline,
            turn_count=len(turns),
            memory_id=int(mid) if mid else None,
        )

    return {
        "success": True,
        "created": not bool(res.get("deduped")),
        "deduped": bool(res.get("deduped")),
        "refreshed": refreshed,
        "date_ist": d,
        "turn_count": len(turns),
        "digest": digest[:500],
        "memory_id": mid,
        "warm": warm_out,
    }


def upsert_week_summary(
    week_start_ist: str,
    week_end_ist: str,
    *,
    with_embeddings: bool = False,
    lazy_day_diaries: bool = True,
) -> dict[str, Any]:
    """Factual multi-day synthesis from day digests + week turn counts."""
    from services.memory.pg_repository import (
        create_memory_pg_idempotent,
        is_postgres_available,
        update_memory_content_pg,
        update_memory_metadata_pg,
    )

    try:
        start_d = date.fromisoformat(week_start_ist)
        end_d = date.fromisoformat(week_end_ist)
    except ValueError:
        return {"success": False, "reason": "invalid_week_bounds"}
    if end_d < start_d:
        return {"success": False, "reason": "week_end_before_start"}

    day_rows: list[dict[str, Any]] = []
    cur = start_d
    while cur <= end_d:
        ds = cur.isoformat()
        if lazy_day_diaries:
            upsert_day_summary(ds, with_embeddings=False)
        row = get_day_summary_row(ds)
        digest = ""
        turn_count = 0
        if row:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            digest = (meta.get("digest") or "").strip()
            if not digest:
                content = row.get("content") or ""
                m = re.search(r"Digest:\s*(.+?)(?:\nTimeline:|$)", content, re.S)
                digest = (m.group(1).strip() if m else _truncate(content, 200))
            turn_count = int(meta.get("turn_count") or 0)
        day_rows.append(
            {
                "date_ist": ds,
                "turn_count": turn_count,
                "digest": _truncate(digest, 220),
                "has_diary": bool(row),
            }
        )
        cur += timedelta(days=1)

    total_turns = sum(int(x.get("turn_count") or 0) for x in day_rows)
    active_days = [x for x in day_rows if x.get("has_diary") or int(x.get("turn_count") or 0) > 0]
    synthesis_lines = [
        f"{x['date_ist']}: turns={x.get('turn_count') or 0} digest={x.get('digest') or '-'}"
        for x in day_rows
    ]
    content = (
        f"Week diary {week_start_ist}..{week_end_ist} IST. "
        f"active_days={len(active_days)} turn_count_total={total_turns}.\n"
        + "\n".join(synthesis_lines)
    )
    if len(content) > 3500:
        content = content[:3497] + "..."

    pg = is_postgres_available() or {}
    if not pg.get("available"):
        return {
            "success": False,
            "reason": pg.get("reason") or "postgres_unavailable",
            "week_start_ist": week_start_ist,
            "week_end_ist": week_end_ist,
            "day_rows": day_rows,
        }

    vector = None
    embed_model = None
    if with_embeddings:
        try:
            from services.memory.embedding_provider import embed_text

            emb = embed_text(content) or {}
            vector = emb.get("vector")
            embed_model = emb.get("model")
            if vector and len(vector) != 3072:
                vector = None
        except Exception:
            vector = None

    dedupe = f"neena_week_{week_start_ist}_{week_end_ist}"
    meta = {
        "section": "week",
        "week_start_ist": week_start_ist,
        "week_end_ist": week_end_ist,
        "turn_count_total": total_turns,
        "active_days": len(active_days),
        "title": f"Week {week_start_ist}",
    }

    try:
        res = create_memory_pg_idempotent(
            write_dedupe_key=dedupe,
            memory_type=TYPE_WEEK_SUMMARY,
            content=content,
            owner_confirmed=True,
            importance=3,
            source="system_week_diary",
            retention="permanent",
            sensitivity_level="normal",
            metadata=meta,
            embedding_model=embed_model if vector else None,
            embedding_vector=vector,
            actor_role="owner",
            subject_key="owner",
            salience=0.7,
        )
    except Exception as exc:
        logger.warning("upsert_week_summary failed: %s", type(exc).__name__)
        return {
            "success": False,
            "reason": type(exc).__name__,
            "day_rows": day_rows,
        }

    if not res.get("success"):
        return {
            "success": False,
            "reason": res.get("reason") or "write_failed",
            "day_rows": day_rows,
        }

    refreshed = False
    if res.get("deduped"):
        mid = (res.get("memory") or {}).get("id")
        old = (res.get("memory") or {}).get("content") or ""
        if mid and old != content:
            try:
                update_memory_content_pg(int(mid), content)
                update_memory_metadata_pg(int(mid), meta)
                refreshed = True
            except Exception as exc:
                logger.debug("week diary refresh skip: %s", type(exc).__name__)

    return {
        "success": True,
        "created": not bool(res.get("deduped")),
        "deduped": bool(res.get("deduped")),
        "refreshed": refreshed,
        "week_start_ist": week_start_ist,
        "week_end_ist": week_end_ist,
        "turn_count_total": total_turns,
        "day_rows": day_rows,
        "memory_id": (res.get("memory") or {}).get("id"),
        "content_preview": _truncate(content, 400),
    }


def seed_yesterday_day_summary(*, with_embeddings: bool = False) -> dict[str, Any]:
    """Catch-up: upsert yesterday IST diary if turns exist."""
    yesterday = (_now_ist().date() - timedelta(days=1)).isoformat()
    return upsert_day_summary(yesterday, with_embeddings=with_embeddings)


def build_day_recall_packet(
    message: str,
    *,
    now: datetime | None = None,
    lazy_diary: bool = True,
) -> dict[str, Any]:
    """Facts for DAY_MEMORY_RECALL — humanize elsewhere."""
    window = resolve_day_window(message, now=now)
    if not window.get("ok"):
        packet = {
            "tool": "day_memory_recall",
            "status": window.get("status") or "needs_clarification",
            "reason": window.get("reason"),
            "hint": (
                "Ask with aaj/kal/parso/N din pehle/pichhle mangal/"
                "YYYY-MM-DD or this week."
            ),
        }
        return {
            "factual_packet": packet,
            "fallback_line": (
                f"Day memory needs clarification. reason={window.get('reason')}. "
                "Use aaj, kal, parso, N din pehle, pichhle weekday, YYYY-MM-DD, or this week."
            ),
            "action_type": "DAY_MEMORY_RECALL",
        }

    turns = list_owner_turns_for_window(
        window["start_utc"],
        window["end_utc"],
        limit=40,
    )
    diary = None
    diary_upsert = None
    week_diary = None
    week_upsert = None
    day_digests: list[dict[str, Any]] | None = None
    intentions: list[dict[str, Any]] = []

    if window.get("kind") == "day" and window.get("date_ist"):
        diary_row = get_day_summary_row(window["date_ist"])
        if not diary_row and lazy_diary and turns:
            diary_upsert = upsert_day_summary(window["date_ist"], with_embeddings=False)
            diary_row = get_day_summary_row(window["date_ist"])
        if diary_row:
            diary = {
                "id": diary_row.get("id"),
                "date_ist": window["date_ist"],
                "content": _truncate(diary_row.get("content") or "", 800),
            }
        try:
            from services.memory.future_intention import list_active_intentions

            intentions = list_active_intentions(
                limit=10, target_date_ist=window.get("date_ist"), status="open"
            )
            # Exact thread_key siblings (equality join only — no keyword NLU).
            thread_keys = sorted(
                {
                    (i.get("thread_key") or "").strip().lower()
                    for i in intentions
                    if (i.get("thread_key") or "").strip()
                }
            )
            thread_siblings: list[dict[str, Any]] = []
            seen_ids = {i.get("id") for i in intentions}
            for tk in thread_keys[:5]:
                for sib in list_active_intentions(limit=8, status="open", thread_key=tk):
                    if sib.get("id") in seen_ids:
                        continue
                    seen_ids.add(sib.get("id"))
                    thread_siblings.append(sib)
        except Exception:
            intentions = []
            thread_siblings = []
    else:
        thread_siblings = []

    if window.get("kind") == "week" and window.get("week_start_ist") and window.get("week_end_ist"):
        if lazy_diary:
            week_upsert = upsert_week_summary(
                window["week_start_ist"],
                window["week_end_ist"],
                with_embeddings=False,
                lazy_day_diaries=True,
            )
            day_digests = (week_upsert or {}).get("day_rows")
        week_row = get_week_summary_row(window["week_start_ist"], window["week_end_ist"])
        if week_row:
            week_diary = {
                "id": week_row.get("id"),
                "week_start_ist": window["week_start_ist"],
                "week_end_ist": window["week_end_ist"],
                "content": _truncate(week_row.get("content") or "", 900),
            }
        elif week_upsert and week_upsert.get("content_preview"):
            week_diary = {
                "id": week_upsert.get("memory_id"),
                "week_start_ist": window["week_start_ist"],
                "week_end_ist": window["week_end_ist"],
                "content": week_upsert.get("content_preview"),
            }

    packet: dict[str, Any] = {
        "tool": "day_memory_recall",
        "status": "ok",
        "timezone": "Asia/Kolkata",
        "kind": window.get("kind"),
        "label": window.get("label"),
        "date_ist": window.get("date_ist"),
        "week_start_ist": window.get("week_start_ist"),
        "week_end_ist": window.get("week_end_ist"),
        "start_utc": window["start_utc"],
        "end_utc": window["end_utc"],
        "turn_count": len(turns),
        "turns": turns[:40],
        "diary": diary,
        "diary_upsert": diary_upsert,
        "week_diary": week_diary,
        "week_upsert": {
            "success": (week_upsert or {}).get("success"),
            "turn_count_total": (week_upsert or {}).get("turn_count_total"),
            "memory_id": (week_upsert or {}).get("memory_id"),
        }
        if week_upsert
        else None,
        "day_digests": day_digests,
        "intentions": intentions,
        "thread_siblings": thread_siblings if window.get("kind") == "day" else [],
    }

    if not turns and not diary and not week_diary and not intentions:
        fallback = (
            f"Day memory empty. label={window.get('label')} "
            f"date_ist={window.get('date_ist')} turn_count=0."
        )
    else:
        fallback = (
            f"Day memory. label={window.get('label')} date_ist={window.get('date_ist')} "
            f"kind={window.get('kind')} turn_count={len(turns)} "
            f"diary={'yes' if diary else 'no'} week_diary={'yes' if week_diary else 'no'} "
            f"intentions={len(intentions)}.\n"
            f"{_factual_timeline(turns[:20])}"
        )
        if diary and diary.get("content"):
            fallback += f"\nDiary: {diary['content']}"
        if week_diary and week_diary.get("content"):
            fallback += f"\nWeek diary: {week_diary['content']}"
        if intentions:
            fallback += "\nIntentions: " + "; ".join(
                f"id={i.get('id')} {(i.get('content') or '')[:80]}" for i in intentions[:8]
            )

    return {
        "factual_packet": packet,
        "fallback_line": fallback,
        "action_type": "DAY_MEMORY_RECALL",
    }


__all__ = [
    "TYPE_DAY_SUMMARY",
    "TYPE_WEEK_SUMMARY",
    "OWNER_DAY_CHANNELS",
    "is_day_memory_question",
    "resolve_day_window",
    "list_owner_turns_for_window",
    "get_day_summary_row",
    "get_week_summary_row",
    "upsert_day_summary",
    "upsert_week_summary",
    "warm_compress_day_summary",
    "seed_yesterday_day_summary",
    "build_day_recall_packet",
]

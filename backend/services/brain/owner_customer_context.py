"""Owner-only customer WhatsApp recall helpers (data → JSON packet).

No phrase/regex NLU. Classification is interpreter → catalog tool
`customer_whatsapp_recall`. Phone digits are optional slot extractors only.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

# Slot extractor only (allowed): pull Indian mobile digits from owner message
# when interpreter left phone_digits empty. Not used for intent routing.
_PHONE_RE = re.compile(r"(?:\+?91[\s-]*)?([6-9][\d\s-]{8,14}\d)")
_LABEL_RE = re.compile(
    r"^\[customer\s+(.+?)(?:\s+\+91\*+\d{2,4})?\]\s*",
    re.I,
)
_MASKED_TAIL_RE = re.compile(r"\+91\*+(\d{2,4})")
_SESSION_PHONE_RE = re.compile(r"whatsapp-customer-(\d{4,15})-", re.I)
IST = timezone(timedelta(hours=5, minutes=30))


def extract_phone_digits(message: str) -> str:
    """Return last-10 national digits if a plausible Indian mobile is present."""
    m = _PHONE_RE.search(message or "")
    if not m:
        return ""
    digits = "".join(c for c in m.group(1) if c.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def _day_bounds_utc(d: date) -> tuple[str, str]:
    start_ist = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    return (
        start_ist.astimezone(timezone.utc).isoformat(),
        end_ist.astimezone(timezone.utc).isoformat(),
    )


def _resolve_window(
    *,
    date_ist: str = "",
    window: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Default = today IST. window=yesterday|today or date_ist=YYYY-MM-DD."""
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    today = base.astimezone(IST).date()
    win = (window or "").strip().lower()
    raw_date = (date_ist or "").strip()
    target = today
    label = "today_ist"
    if raw_date:
        try:
            target = date.fromisoformat(raw_date[:10])
            label = raw_date[:10]
        except ValueError:
            target = today
            label = "today_ist"
    elif win in ("yesterday", "kal"):
        target = today - timedelta(days=1)
        label = "yesterday_ist"
    elif win in ("today", "aaj", ""):
        target = today
        label = "today_ist"
    start_utc, end_utc = _day_bounds_utc(target)
    return {
        "date_ist": target.isoformat(),
        "window_label": label,
        "start_utc": start_utc,
        "end_utc": end_utc,
    }


def _listener_turns_for_window(
    start_utc: str,
    end_utc: str,
    *,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """IST-day (or explicit) whatsapp_listener turns — not last-N global."""
    try:
        import database as db

        return list(
            db.list_command_center_turns_between(
                start_utc,
                end_utc,
                limit=max(1, min(int(limit), 200)),
                channels=["whatsapp_listener"],
            )
            or []
        )
    except Exception:
        return []


def _recent_listener_turns_from_recorder(limit: int = 12) -> list[dict[str, Any]]:
    """Legacy helper (tests/back-compat). Prefer day-window path in packet builder."""
    try:
        import database as db

        turns = db.list_command_center_turns(limit=max(limit * 3, 40))
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for turn in turns:
        if (turn.get("channel") or "") != "whatsapp_listener":
            continue
        out.append(turn)
        if len(out) >= limit:
            break
    return out


def _contact_from_turn(turn: dict[str, Any]) -> dict[str, str]:
    raw_in = turn.get("user_input") or ""
    name = "ji"
    phone = ""
    m = _LABEL_RE.match(raw_in)
    if m:
        name = (m.group(1) or "ji").strip() or "ji"
    mt = _MASKED_TAIL_RE.search(raw_in)
    masked_tail = mt.group(1) if mt else ""
    sm = _SESSION_PHONE_RE.search(str(turn.get("session_id") or ""))
    if sm:
        digits = "".join(c for c in sm.group(1) if c.isdigit())
        if len(digits) >= 10:
            phone = digits[-10:]
        elif digits:
            phone = digits
    body = _LABEL_RE.sub("", raw_in).strip()
    return {
        "name": name[:80],
        "phone_last10": phone,
        "masked_tail": masked_tail,
        "in": body[:240] or raw_in[:240],
        "out": (turn.get("assistant_reply") or "")[:240],
        "at": str(turn.get("created_at") or ""),
    }


def _aggregate_contacts(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for turn in turns:
        c = _contact_from_turn(turn)
        key = c["phone_last10"] or f"name:{(c['name'] or 'ji').lower()}"
        if key not in buckets:
            order.append(key)
            buckets[key] = {
                "name": c["name"],
                "phone_last10": c["phone_last10"] or None,
                "masked_tail": c["masked_tail"] or None,
                "turn_count": 0,
                "last_in": "",
                "last_out": "",
                "last_at": "",
            }
        b = buckets[key]
        b["turn_count"] = int(b["turn_count"]) + 1
        if c["name"] and c["name"] != "ji":
            b["name"] = c["name"]
        b["last_in"] = c["in"]
        b["last_out"] = c["out"]
        b["last_at"] = c["at"]
    return [buckets[k] for k in order]


def build_customer_recall_packet(
    *,
    phone_digits: str = "",
    owner_message: str = "",
    limit: int = 40,
    date_ist: str = "",
    window: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Checked facts for customer WhatsApp — never invent; empty is explicit."""
    phone = (phone_digits or "").strip()
    if len(phone) >= 10:
        phone = "".join(c for c in phone if c.isdigit())[-10:]
    elif not phone:
        phone = extract_phone_digits(owner_message or "")

    bounds = _resolve_window(date_ist=date_ist, window=window, now=now)
    recorder_turns = _listener_turns_for_window(
        bounds["start_utc"],
        bounds["end_utc"],
        limit=max(int(limit), 200),
    )
    if phone:
        filtered: list[dict[str, Any]] = []
        for t in recorder_turns:
            c = _contact_from_turn(t)
            if c["phone_last10"] == phone or (
                c["masked_tail"] and phone.endswith(c["masked_tail"])
            ):
                filtered.append(t)
        recorder_turns = filtered

    contacts = _aggregate_contacts(recorder_turns)
    summarized: list[dict[str, str]] = []
    for turn in recorder_turns[-min(len(recorder_turns), 30) :]:
        c = _contact_from_turn(turn)
        summarized.append(
            {
                "at": c["at"],
                "name": c["name"],
                "phone_last10": c["phone_last10"],
                "in": c["in"],
                "out": c["out"],
            }
        )

    redis_turns: list[dict[str, str]] = []
    if phone:
        try:
            from services.brain.redis_state import get_customer_chat_turns

            redis_turns = get_customer_chat_turns(phone, limit=8) or []
        except Exception:
            redis_turns = []

    turn_count = len(recorder_turns)
    redis_count = len(redis_turns)
    has_any = turn_count > 0 or redis_count > 0
    packet: dict[str, Any] = {
        "tool": "customer_whatsapp_recall",
        "status": "ok" if has_any else "empty",
        "checked": True,
        "channel": "whatsapp_listener",
        "window": bounds["window_label"],
        "date_ist": bounds["date_ist"],
        "phone_digits": phone or None,
        "contact_count": len(contacts),
        "contacts": contacts,
        "redis_turn_count": redis_count,
        "recorder_turn_count": turn_count,
        "recorder_turns": summarized,
        "note": (
            "Neena talks to customers on WhatsApp only, not voice calls. "
            "Summarize ONLY these checked turns/contacts; if empty, say checked "
            f"window={bounds['date_ist']} IST and found none. Never invent."
        ),
    }
    if phone and redis_turns:
        packet["redis_thread"] = [
            {
                "who": "Customer" if t.get("role") == "user" else "Neena",
                "text": (t.get("text") or "")[:240],
            }
            for t in redis_turns
        ]

    if has_any:
        names = ", ".join(
            f"{c.get('name')}"
            + (f" (..{c['phone_last10'][-4:]})" if c.get("phone_last10") else "")
            for c in contacts[:8]
        )
        fallback = (
            f"Sir, {bounds['date_ist']} IST window check kiya — "
            f"{len(contacts)} contact, {turn_count} recorder turn"
            + (f": {names}." if names else ".")
            + (
                f" +91{phone} Redis thread me {redis_count} turn."
                if phone and redis_count
                else ""
            )
        )
    else:
        fallback = (
            f"Sir, {bounds['date_ist']} IST window me customer WhatsApp recorder check "
            f"kiya — koi customer message nahi mila."
            + (f" +91{phone} ka Redis thread bhi empty." if phone else "")
        )

    return {
        "action_type": "CUSTOMER_WHATSAPP_RECALL",
        "factual_packet": packet,
        "fallback_line": fallback,
    }


# Back-compat for older imports/tests — text block from the same checked facts.
def build_owner_customer_context_block(message: str) -> str | None:
    out = build_customer_recall_packet(owner_message=message or "")
    pkt = out.get("factual_packet") or {}
    lines = [
        "CUSTOMER WHATSAPP THREADS (owner-only visibility — never invent; "
        "Neena talks to customers on WhatsApp only, not voice calls):",
        f"checked={pkt.get('checked')} status={pkt.get('status')} "
        f"date_ist={pkt.get('date_ist')} recorder_turn_count={pkt.get('recorder_turn_count')} "
        f"contact_count={pkt.get('contact_count')}",
    ]
    for c in pkt.get("contacts") or []:
        lines.append(
            f"  CONTACT: {c.get('name')} phone={c.get('phone_last10')} "
            f"turns={c.get('turn_count')} last_in={c.get('last_in')}"
        )
    for t in pkt.get("recorder_turns") or []:
        lines.append(f"  IN: {t.get('in')}")
        if t.get("out"):
            lines.append(f"  OUT: {t.get('out')}")
    if pkt.get("status") == "empty":
        lines.append(
            f"Customer WhatsApp turns for {pkt.get('date_ist')} IST: NONE. "
            "Say you checked and found none — do not invent chats."
        )
    return "\n".join(lines)


__all__ = [
    "build_customer_recall_packet",
    "build_owner_customer_context_block",
    "extract_phone_digits",
]

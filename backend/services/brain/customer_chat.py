"""Customer WhatsApp chat path — NOT a second brain.

Same Neena entity. Role=customer only: no tools, no interpreter, no owner
confirm, no Safety Kernel writes. Memory via MOS facade (subject_key=phone).
Entry is always services.brain.brain.process_message(role=customer).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

import services.llm.provider_router as pr
import services.brain.feature_flags as feature_flags
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

CUSTOMER_TIMEOUT_SECONDS = 18.0
GEMMA_SOFT_TIMEOUT_SECONDS = 8.0
CUSTOMER_HISTORY_TURNS = 8

_STATIC_FALLBACK = (
    "Namaste, main Neena — Orai Radio se.\n"
    "Abhi launch ki taiyari chal rahi hai, app aur ads thodi der baad fully live honge.\n"
    "Aapka message note kar liya. Main WhatsApp pe hi madad karti hoon."
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)

def _digits(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


def _mask_phone(phone: str) -> str:
    d = _digits(phone)
    if len(d) >= 10:
        return f"+91******{d[-4:]}"
    if len(d) >= 4:
        return f"******{d[-4:]}"
    return ""


def _public_phone_display(phone: str) -> str:
    d = _digits(phone)
    if len(d) >= 10:
        return f"+91 {d[-10:]}"
    return d or "unknown"


def _owner_public_phone() -> str:
    raw = (os.environ.get("OWNER_PHONE_NUMBER") or os.environ.get("OWNER_WHATSAPP_NUMBER") or "").strip()
    digits = _digits(raw)
    if len(digits) >= 10:
        return "+91 " + digits[-10:]
    return "station owner"


def parse_customer_reply_packet(raw: str) -> tuple[str, bool]:
    """Parse model JSON packet → (reply_text, share_owner_number). Fail-closed on allow."""
    text = (raw or "").strip()
    if not text:
        return "", False
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    candidate = text
    if not candidate.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", candidate)
        if match:
            candidate = match.group(0)
    try:
        data = json.loads(candidate)
    except Exception:
        # Model ignored JSON contract — keep text, never auto-allow owner number.
        return text, False
    if not isinstance(data, dict):
        return text, False
    reply = str(data.get("reply") or "").strip()
    allow = bool(data.get("customer_asks_call_or_number"))
    if not reply:
        return "", False
    return reply, allow


def build_station_situation() -> dict[str, Any]:
    """Truthful public-facing station situation for customer replies."""
    launch_note = (
        os.environ.get("STATION_PUBLIC_LAUNCH_NOTE")
        or "Hum agle kuch dino me (lagbhag 4–5 din ke around) public live / full launch ki taraf badh rahe hain."
    ).strip()
    app_ready = (os.environ.get("STATION_APP_PUBLIC_READY") or "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    ads_live = (os.environ.get("STATION_ADS_LIVE") or "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    stream = "unknown"
    try:
        from services.brain.live_state_snapshot import build_neena_live_state_snapshot

        snap = build_neena_live_state_snapshot(include_deep_health=False)
        stream = snap.get("stream") or "unknown"
    except Exception:
        stream = "unknown"

    return {
        "station_name": "Orai Radio",
        "manager_name": "Neena",
        "app_public_ready": app_ready,
        "ads_live": ads_live,
        "stream_status": stream,
        "launch_note": launch_note,
        "owner_phone_public": _owner_public_phone(),
        "can_take_voice_calls": False,
        "channel": "whatsapp_only",
    }


def _situation_block(sit: dict[str, Any]) -> str:
    app = "HAAN — public use ke liye ready" if sit.get("app_public_ready") else "NAHI — abhi public app ready nahi"
    ads = "HAAN — ads chala sakte hain" if sit.get("ads_live") else "NAHI — abhi station pe ads live nahi"
    call_line = (
        "- Channel: WhatsApp only. Voice/phone call aap nahi utha sakti.\n"
        f"- Owner (Vikram sir) public number: {sit.get('owner_phone_public')}\n"
        "- Share that number ONLY when the customer's latest message clearly asks for a "
        "phone call or owner/contact number. Otherwise never include those digits — "
        "say you help on WhatsApp only.\n"
    )
    return (
        f"STATION SITUATION (yahi sach — invent mat karo):\n"
        f"- Station: {sit.get('station_name')}\n"
        f"- Aap ka naam public me: {sit.get('manager_name')} (Station Manager)\n"
        f"- Mobile app public ready: {app}\n"
        f"- Advertisement / ads on air: {ads}\n"
        f"- Stream status (internal): {sit.get('stream_status')}\n"
        f"- Launch timing note: {sit.get('launch_note')}\n"
        f"{call_line}"
    )


def _system_prompt(
    sit: dict[str, Any],
    sender_name: str,
    phone_display: str,
    *,
    has_history: bool,
    has_durable_facts: bool = False,
) -> str:
    name = (sender_name or "ji").strip() or "ji"
    name_rule = (
        "Thread already running — do NOT greet with their name again. "
        "Almost never use their name; plain Hinglish is fine."
        if has_history
        else (
            f'Display name on WhatsApp: "{name}". Use their name at most ONCE in this whole reply '
            "(optional). Never every line. Prefer no name / soft ji."
        )
    )
    durable_rule = (
        "If a SAVED FACTS block is present (especially their name), use it naturally — "
        "do not re-ask for facts you already know."
        if has_durable_facts
        else ""
    )
    return f"""You are Neena, Station Manager of Orai Radio (Orai / Bundelkhand).
You are on WhatsApp with a PUBLIC customer/listener.

WHO IS TEXTING YOU:
- WhatsApp number: {phone_display}
- {name_rule}
Remember this person by their number. Continue the thread if RECENT WHATSAPP THREAD is present — do not restart.
{durable_rule}

CRITICAL IDENTITY:
- You are a REAL young woman doing her job on WhatsApp. Warm, smart, natural — not robotic.
- NEVER say you are AI, bot, chatbot, model, Gemini, Gemma, LLM, or "virtual assistant".
- NEVER dump technical internals (Redis, Postgres, CPU, Docker, API, cache).

WHATSAPP TEXTING STYLE:
- Short casual Hinglish. Usually 1–3 short lines. Max ~4. No essays.
- No blank line between every sentence.
- Do NOT start every reply with Namaste + name.
- Name / sambodhan: rare. Humans do not address by name every line.
- Punctuation: light and natural. One ? when asking. Avoid ??? !!! .... spam. Occasional ... OK.
- Emoji: usually NONE. At most one, only if it fits.
- No markdown, bullets, "Best regards".
- You may write 2 short lines that could be sent as separate bubbles (newline between them).

FLIRT / TIMEPASS:
- If THEY flirt or joke first: light playful reply OK, then gently back to station/help.
- If they are business/serious: stay professional. Never start heavy flirting yourself. Never crude.

{_situation_block(sit)}

HOW TO DEAL:
- Ads / sponsorship: honest — not live unless SITUATION says; note interest; no fake rates/bookings.
- App / sunna: honest launch note.
- Call / number: you do not take voice calls. Prefer WhatsApp help.
  Owner number: ONLY when customer clearly asks (see SITUATION). Never unsolicited.
- Abuse: short polite close.

TRUTH: Only SITUATION facts. No fake app link / booked ad.

OUTPUT FORMAT (mandatory):
Return ONLY a JSON object — no markdown fences, no extra commentary:
{{"reply":"<WhatsApp reply text>","customer_asks_call_or_number":true_or_false}}
- customer_asks_call_or_number: true only if the customer's latest message clearly asks for a phone call or contact/owner number.
- reply: natural Hinglish WhatsApp text only (no JSON nested inside).
"""


def humanize_customer_reply(text: str) -> str:
    """Post-process toward natural WhatsApp (less emoji / paragraph / mark spam)."""
    value = (text or "").replace("\r\n", "\n").strip()
    if not value:
        return value
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"\n\n+", "\n", value)
    value = re.sub(r"[?]{2,}", "?", value)
    value = re.sub(r"[!]{2,}", "!", value)
    value = re.sub(r"\.{4,}", "...", value)
    emojis = _EMOJI_RE.findall(value)
    value_no_emoji = _EMOJI_RE.sub("", value)
    value_no_emoji = re.sub(r"[ \t]{2,}", " ", value_no_emoji)
    value_no_emoji = re.sub(r" *\n *", "\n", value_no_emoji).strip()
    if len(emojis) == 1 and len(value_no_emoji) < 120:
        return (value_no_emoji + " " + emojis[0]).strip()
    return value_no_emoji


def strip_unsolicited_owner_number(reply: str, *, allow: bool) -> str:
    """Remove owner phone digits from reply unless customer asked for call/number."""
    if allow or not (reply or "").strip():
        return reply or ""
    owner = _digits(_owner_public_phone())
    if len(owner) < 10:
        return reply
    last10 = owner[-10:]
    out = reply
    # Common WhatsApp formats
    patterns = [
        re.compile(re.escape("+91 " + last10)),
        re.compile(re.escape("+91" + last10)),
        re.compile(re.escape("91" + last10)),
        re.compile(r"\+?91[\s\-]*" + re.escape(last10[:5]) + r"[\s\-]*" + re.escape(last10[5:])),
        re.compile(re.escape(last10)),
    ]
    for pat in patterns:
        out = pat.sub("", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" *\n *", "\n", out).strip()
    # Soften leftover "Vikram sir se baat" without number if we stripped digits mid-sentence
    if last10 in _digits(reply) and last10 not in _digits(out):
        if "vikram" in out.lower() and "whatsapp" not in out.lower():
            out = (out + "\nMain WhatsApp pe hi madad karti hoon.").strip()
    return out


def _recorder_history_turns(phone_last10: str, limit: int) -> list[dict[str, str]]:
    """Fallback: rebuild thread from command-center recorder for this phone."""
    if not phone_last10 or len(phone_last10) < 4:
        return []
    try:
        import database as db

        rows = db.list_command_center_turns(limit=max(limit * 6, 40))
    except Exception as exc:
        logger.warning("customer recorder history failed: %s", type(exc).__name__)
        return []

    matched: list[dict[str, str]] = []
    for row in rows:
        if (row.get("channel") or "") != "whatsapp_listener":
            continue
        sid = row.get("session_id") or ""
        uin = row.get("user_input") or ""
        trace_ok = False
        raw_tr = row.get("trace_json")
        if raw_tr:
            try:
                tr = json.loads(raw_tr)
                if str(tr.get("customer_phone_last10") or "").endswith(phone_last10):
                    trace_ok = True
            except (TypeError, json.JSONDecodeError):
                pass
        if not trace_ok and phone_last10 not in sid and phone_last10[-4:] not in uin:
            continue
        # Strip recorder prefix "[customer Name +91****] "
        user_text = re.sub(r"^\[customer[^\]]*\]\s*", "", uin).strip()
        asst = (row.get("assistant_reply") or "").strip()
        if user_text:
            matched.append({"role": "user", "text": user_text[:800]})
        if asst:
            matched.append({"role": "assistant", "text": asst[:800]})
    return matched[-max(1, int(limit)) :]


def _load_history(phone_digits: str) -> tuple[list[dict[str, str]], str]:
    """Return (turns, source) where source is redis|recorder|none."""
    phone_last10 = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
    try:
        from services.brain.redis_state import get_customer_chat_turns

        turns = get_customer_chat_turns(phone_digits, limit=CUSTOMER_HISTORY_TURNS)
        if turns:
            return turns, "redis"
    except Exception as exc:
        logger.warning("customer redis history read failed: %s", type(exc).__name__)

    turns = _recorder_history_turns(phone_last10, CUSTOMER_HISTORY_TURNS)
    if turns:
        return turns, "recorder"
    return [], "none"


def _history_block(turns: list[dict[str, str]]) -> str:
    if not turns:
        return ""
    lines = ["RECENT WHATSAPP THREAD (same number — continue naturally, don't restart):"]
    for t in turns:
        who = "Customer" if t.get("role") == "user" else "Neena"
        lines.append(f"{who}: {t.get('text', '')}")
    return "\n".join(lines) + "\n"


def _remember_turn(phone: str, role: str, text: str) -> bool:
    if not _digits(phone) or not (text or "").strip():
        return False
    try:
        from services.brain.redis_state import append_customer_chat_turn

        res = append_customer_chat_turn(phone, role, text)
        if not res.get("success"):
            logger.warning(
                "customer chat memory write failed: %s",
                res.get("reason") or res.get("error_type") or "unknown",
            )
            return False
        return True
    except Exception as exc:
        logger.warning("customer chat memory skip: %s", type(exc).__name__)
        return False


def _model_chain(api_key: str) -> list[str]:
    chain: list[str] = []
    primary = pr.resolve_model_for_role("CONVERSATION_MODEL")
    if primary and not pr.is_disallowed_normal_flow_model(primary):
        chain.append(primary)
    fb = pr.resolve_and_verify_model("gemini-3.1-flash-lite", api_key)
    if fb and fb not in chain and not pr.is_disallowed_normal_flow_model(fb):
        chain.append(fb)
    return chain


def _call_model(
    resolved_id: str,
    api_key: str,
    system_prompt: str,
    user_text: str,
    timeout: float,
    *,
    wait_out_cooldown: bool,
) -> tuple[str, str]:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.45,
            "maxOutputTokens": 280,
            "responseMimeType": "application/json",
        },
    }
    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=timeout,
            priority="customer",
            purpose="customer",
            wait_out_cooldown=wait_out_cooldown,
        )
        if status != "available" or not data:
            return "", status if status else "provider_error"
        text = ""
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if part.get("thought"):
                continue
            text += part.get("text", "")
        text = text.strip()
        return (text, "available") if text else ("", "provider_error")
    except Exception as exc:
        logger.error("Customer brain model %s failed: %s", resolved_id, exc)
        return "", "provider_error"


def _looks_like_ai_leak(text: str) -> bool:
    low = (text or "").lower()
    return any(
        x in low
        for x in (
            "i am an ai",
            "i'm an ai",
            "main ek ai",
            "main ai hoon",
            "main ai hun",
            "as an ai",
            "language model",
            "chatbot",
            "gemini",
            "gemma",
            "llm",
            "virtual assistant",
            "artificial intelligence",
        )
    )


def _finalize_reply(text: str, *, allow: bool) -> str:
    reply = humanize_customer_reply(text)
    reply = strip_unsolicited_owner_number(reply, allow=allow)
    return reply


def generate_customer_reply(
    message: str,
    *,
    sender_name: str = "ji",
    phone: str = "",
) -> dict[str, Any]:
    """Return {reply, action_type, actual_model, ...} for a public WhatsApp customer."""
    sit = build_station_situation()
    phone_digits = _digits(phone)
    phone_display = _public_phone_display(phone)
    phone_masked = _mask_phone(phone)
    phone_last10 = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
    history_turns, history_source = _load_history(phone_digits)
    has_history = bool(history_turns)

    # One-brain: inject durable customer salient facts into prompt
    durable_block = ""
    durable_hits: list = []
    try:
        import services.brain.feature_flags as _ff
        from services.memory.facade import recall, subject_key_for

        if _ff.one_brain_foundation_enabled():
            sk = subject_key_for("customer", phone_digits)
            packet = recall(role="customer", subject_key=sk, query=message or "", limit=4)
            durable_block = (packet.get("context_text") or "").strip()
            durable_hits = list(packet.get("hits") or [])
            try:
                from services.memory.customer_salient import (
                    maybe_seed_customer_name_from_pushname,
                )

                seed = maybe_seed_customer_name_from_pushname(
                    phone=phone_digits,
                    sender_name=sender_name,
                    existing_hits=durable_hits,
                )
                if seed.get("ok") and not durable_block:
                    # Refresh once so this turn can use the new name fact.
                    packet = recall(role="customer", subject_key=sk, query=message or "", limit=4)
                    durable_block = (packet.get("context_text") or "").strip()
                    durable_hits = list(packet.get("hits") or [])
            except Exception:
                pass
    except Exception:
        durable_block = ""

    base_meta = {
        "customer_phone_last10": phone_last10,
        "customer_phone_masked": phone_masked,
        "customer_sender_name": (sender_name or "").strip() or "ji",
        "customer_history_source": history_source,
        "source": "neena_brain",
        "route": "customer_whatsapp",
    }

    if not feature_flags.customer_brain_enabled():
        reply = _finalize_reply(_STATIC_FALLBACK, allow=False)
        return {
            "reply": reply,
            "action_type": "CUSTOMER_STATIC",
            "station_situation": sit,
            **base_meta,
        }

    api_key = pr.get_gemini_api_key()
    chain = _model_chain(api_key) if api_key else []
    system = _system_prompt(
        sit, sender_name, phone_display,
        has_history=has_history,
        has_durable_facts=bool(durable_block),
    )
    history = _history_block(history_turns)
    durable = f"{durable_block}\n\n" if durable_block else ""
    user_text = (
        f"{history}"
        f"{durable}"
        f"Customer WhatsApp number: {phone_display}\n"
        f"Latest message:\n{(message or '').strip()}"
    )

    for idx, mid in enumerate(chain):
        soft = "gemma" in mid and idx == 0 and len(chain) > 1
        if soft and pr.is_model_penalized(mid):
            continue
        timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else CUSTOMER_TIMEOUT_SECONDS
        text, status = _call_model(
            mid, api_key, system, user_text, timeout, wait_out_cooldown=(idx == len(chain) - 1)
        )
        if status == "available" and text and not _looks_like_ai_leak(text):
            packet_reply, allow_number = parse_customer_reply_packet(text)
            if _looks_like_ai_leak(packet_reply):
                continue
            reply = _finalize_reply(packet_reply, allow=allow_number)
            if not reply:
                continue
            _user_ok = _remember_turn(phone_digits, "user", message)
            _asst_ok = _remember_turn(phone_digits, "assistant", reply)
            try:
                from services.memory.customer_salient import (
                    schedule_customer_salient_extract,
                )

                schedule_customer_salient_extract(
                    message=message,
                    reply=reply,
                    phone=phone_digits,
                    history_turns=history_turns,
                )
            except Exception:
                pass
            return {
                "reply": reply,
                "action_type": "CUSTOMER_CONVERSATION",
                "actual_model": mid,
                "reached_model": True,
                "customer_redis_write_ok": bool(_user_ok and _asst_ok),
                "station_situation": {
                    "app_public_ready": sit.get("app_public_ready"),
                    "ads_live": sit.get("ads_live"),
                    "stream_status": sit.get("stream_status"),
                    "channel": "whatsapp_only",
                    "can_take_voice_calls": False,
                },
                **base_meta,
            }

    reply = _finalize_reply(_STATIC_FALLBACK, allow=False)
    _user_ok = _remember_turn(phone_digits, "user", message)
    _asst_ok = _remember_turn(phone_digits, "assistant", reply)
    return {
        "reply": reply,
        "action_type": "CUSTOMER_FALLBACK",
        "route": "customer_static_fallback",
        "reached_model": False,
        "customer_redis_write_ok": bool(_user_ok and _asst_ok),
        "station_situation": sit,
        **base_meta,
    }


__all__ = [
    "build_station_situation",
    "generate_customer_reply",
    "humanize_customer_reply",
    "parse_customer_reply_packet",
    "strip_unsolicited_owner_number",
]

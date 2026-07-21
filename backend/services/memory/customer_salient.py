"""Customer 1B â€” extract salient/repeated facts after a turn (async best-effort).

Uses conversation LLM JSON only â€” no Hindi keyword NLU for understanding.
Allowlisted types only; never secrets; never owner policy types.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any

import services.brain.feature_flags as feature_flags
from services.memory.contract import ALLOWED_CUSTOMER_SALIENT_TYPES
from services.memory.facade import auto_salient_write, subject_key_for

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = (
    "You extract durable listener facts for a radio station CRM. "
    "Return ONLY JSON: {\"facts\":[{\"memory_type\":\"...\",\"content\":\"...\",\"salience\":1-5}]}. "
    f"memory_type MUST be one of: {sorted(ALLOWED_CUSTOMER_SALIENT_TYPES)}. "
    "Include a fact only if it is a clear name, preference, callback request, complaint topic, "
    "or show interest â€” or clearly repeated across history. "
    "If nothing durable, return {\"facts\":[]}. No secrets, no API keys, no other people's phones."
)

_PLACEHOLDER_NAMES = frozenset(
    {
        "",
        "ji",
        "client",
        "user",
        "unknown",
        "listener",
        "customer",
        "whatsapp",
    }
)


def schedule_customer_salient_extract(
    *,
    message: str,
    reply: str,
    phone: str,
    history_turns: list[dict[str, Any]] | None = None,
) -> None:
    """Fire-and-forget extract so customer reply latency is not blocked on 2nd LLM."""
    try:
        threading.Thread(
            target=maybe_extract_and_store_customer_salient,
            kwargs={
                "message": message,
                "reply": reply,
                "phone": phone,
                "history_turns": list(history_turns or []),
            },
            daemon=True,
            name="customer-salient-extract",
        ).start()
    except Exception:
        # Never break the reply path
        pass


def maybe_seed_customer_name_from_pushname(
    *,
    phone: str,
    sender_name: str,
    existing_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Once per subject: persist WhatsApp display name as customer_name (metadata, not NLU)."""
    try:
        if not feature_flags.customer_salient_memory_enabled():
            return {"ok": False, "skipped": True, "reason": "flag_off"}
        if not feature_flags.one_brain_foundation_enabled():
            return {"ok": False, "skipped": True, "reason": "one_brain_off"}
        name = (sender_name or "").strip()
        if not name or name.lower() in _PLACEHOLDER_NAMES:
            return {"ok": False, "skipped": True, "reason": "placeholder_name"}
        if name.isdigit() or len(name) < 2 or len(name) > 40:
            return {"ok": False, "skipped": True, "reason": "invalid_name"}
        for hit in existing_hits or []:
            if (hit.get("memory_type") or "") == "customer_name":
                return {"ok": False, "skipped": True, "reason": "already_have_name"}
        return auto_salient_write(
            phone=phone,
            memory_type="customer_name",
            content=name,
            source_message="whatsapp_pushname",
            salience=3.0,
        )
    except Exception as exc:
        logger.debug("pushname seed failed: %s", type(exc).__name__)
        return {"ok": False, "reason": type(exc).__name__}


def maybe_extract_and_store_customer_salient(
    *,
    message: str,
    reply: str,
    phone: str,
    history_turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Best-effort; never raises into the customer reply path."""
    try:
        if not feature_flags.customer_salient_memory_enabled():
            return {"ok": False, "skipped": True, "reason": "flag_off"}
        if not feature_flags.one_brain_foundation_enabled():
            return {"ok": False, "skipped": True, "reason": "one_brain_off"}
        sk = subject_key_for("customer", phone)
        if sk == "unknown":
            return {"ok": False, "skipped": True, "reason": "no_phone"}

        # Length gate only â€” skip tiny pings that burn quota (not keyword NLU).
        if len((message or "").strip()) < 4:
            return {"ok": False, "skipped": True, "reason": "message_too_short"}

        facts = _extract_facts(message, reply, history_turns or [])
        saved = []
        for fact in facts:
            mtype = (fact.get("memory_type") or "").strip().lower()
            content = (fact.get("content") or "").strip()
            if mtype not in ALLOWED_CUSTOMER_SALIENT_TYPES or not content:
                continue
            try:
                sal = float(fact.get("salience") or 2)
            except (TypeError, ValueError):
                sal = 2.0
            res = auto_salient_write(
                phone=phone,
                memory_type=mtype,
                content=content,
                source_message=message,
                salience=sal,
            )
            if res.get("ok"):
                saved.append({"memory_type": mtype, "content": content[:80], "id": res.get("memory_id")})
        return {"ok": True, "saved_count": len(saved), "saved": saved, "subject_key": sk, "facts_found": len(facts)}
    except Exception as exc:
        logger.debug("customer salient extract failed: %s", type(exc).__name__)
        return {"ok": False, "reason": type(exc).__name__}


def _extract_facts(
    message: str,
    reply: str,
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    import services.llm.provider_router as pr

    api_key = pr.get_gemini_api_key()
    if not api_key:
        return _heuristic_repeated_name(message, history)

    mid = pr.resolve_model_for_role("CONVERSATION_MODEL")
    if not mid or pr.is_disallowed_normal_flow_model(mid):
        mid = pr.resolve_and_verify_model("gemini-3.1-flash-lite", api_key)
    if not mid:
        return _heuristic_repeated_name(message, history)

    hist_lines = []
    for t in history[-6:]:
        role = t.get("role") or "user"
        text = (t.get("text") or "")[:200]
        if text:
            hist_lines.append(f"{role}: {text}")
    user_blob = (
        f"History:\n" + ("\n".join(hist_lines) or "(none)") + "\n\n"
        f"Latest customer message:\n{(message or '').strip()}\n\n"
        f"Neena reply (context only):\n{(reply or '').strip()[:300]}\n"
    )
    try:
        payload = {
            "systemInstruction": {"parts": [{"text": _EXTRACT_SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": user_blob}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
        }
        data, status, _meta = pr.call_generate_content_json(
            mid,
            api_key,
            payload,
            timeout=8,
            priority="customer",
            purpose="salient",
        )
        if status != "available" or not data:
            return _heuristic_repeated_name(message, history)
        text = (
            ((data.get("candidates") or [{}])[0].get("content") or {})
            .get("parts") or [{}]
        )[0].get("text") or ""
        return _parse_facts_json(text)
    except Exception:
        return _heuristic_repeated_name(message, history)


def _parse_facts_json(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return []
    # Strip markdown fences if any
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except Exception:
            return []
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        return []
    out = []
    for f in facts:
        if isinstance(f, dict):
            out.append(f)
    return out


def _heuristic_repeated_name(message: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Minimal non-NLU fallback: if same short self-name token repeats, store customer_name."""
    # Only exact "mera naam X" style is too keyword-y; instead require repetition of a token
    # that appears as a likely name in 2+ user turns â€” skip if unsure.
    return []


__all__ = [
    "maybe_extract_and_store_customer_salient",
    "schedule_customer_salient_extract",
    "maybe_seed_customer_name_from_pushname",
]

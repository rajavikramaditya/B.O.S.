"""M3-A1 Gemini-based launch operations intent classifier."""
from __future__ import annotations

import json
import logging
import os
import sys

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import services.llm.provider_router as pr
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

CLASSIFIER_TIMEOUT_SECONDS = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.45
MEDIUM_CONFIDENCE_THRESHOLD = 0.65

OPERATION_INTENTS = {
    "station_status",
    "rj_intro",
    "ad_script",
    "daily_show_plan",
    "permanent_memory_save",
    "approval",
    "diagnostics",
    "general_chat",
    "clarification_needed",
}

CLASSIFIER_SYSTEM = """You are Neena Gupta's launch-operations intent classifier for Orai Radio.
Analyze the owner's message and return ONLY valid JSON (no markdown).

Required JSON:
{
  "intent": "station_status | rj_intro | ad_script | daily_show_plan | permanent_memory_save | approval | diagnostics | general_chat | clarification_needed",
  "confidence": 0.0-1.0,
  "extracted_fields": { ... },
  "reason_short": "brief reason"
}

extracted_fields by intent:
- station_status: requested_scope (full|short|health_only)
- rj_intro: show_time, tone, local_touch_requested (bool), length_preference
- ad_script: business_name, duration_seconds (10|20|30), tone, cta_preference, local_touch_requested (bool)
- daily_show_plan: show_type, number_of_segments (3-5), local_updates_needed (bool)
- permanent_memory_save: memory_content_hint
- approval: {}
- diagnostics: {}
- general_chat: {}
- clarification_needed: clarification_question_hint

Guidelines:
- station_status: owner asks how station/system/health is running (status batao, health check, system kaisa chal raha)
- rj_intro: owner wants RJ intro/opening script for a show
- ad_script: owner wants radio advertisement/promo script for a business
- daily_show_plan: owner wants show rundown/content plan with segments
- permanent_memory_save: owner explicitly asks to save something to permanent memory
- approval: owner only says approved/confirm with no other task
- diagnostics: owner asks diagnostics/health scan command
- general_chat: casual chat not matching above
- clarification_needed: request too vague to route (confidence should be low)

Do not invent business names. Extract only what owner said.
Output raw JSON only."""

FALLBACK_PACKET = {
    "intent": "general_chat",
    "confidence": 0.0,
    "extracted_fields": {},
    "reason_short": "classifier_unavailable",
}


def classify_operations_intent(
    user_message: str,
    selected_model: str = "auto",
    memory_context: str = "",
) -> tuple[dict, str, str, str | None]:
    """Returns (packet, provider, status, resolved_model_id)."""
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return dict(FALLBACK_PACKET), "none", "unavailable", None

    model_option = "gemini-3.1-flash-lite" if selected_model == "auto" else selected_model
    resolved_id = pr.resolve_and_verify_model(
        model_option, api_key, allow_network_refresh=False
    )
    if not resolved_id:
        return dict(FALLBACK_PACKET), "none", "model_unavailable", None

    provider = "gemma" if "gemma" in resolved_id else "gemini"
    system_inst = CLASSIFIER_SYSTEM
    if memory_context:
        system_inst += f"\n\nMemory context (for classification only):\n{memory_context[:2000]}"

    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_inst}]},
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
    }
    if "gemini" in resolved_id:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=CLASSIFIER_TIMEOUT_SECONDS,
            priority="owner",
            purpose="interpreter",
        )
        use_id = meta.get("model_id") or resolved_id
        provider = "gemma" if "gemma" in use_id else "gemini"
        if status == "cooldown":
            pkt = {**FALLBACK_PACKET, "reason_short": f"cooldown_{meta.get('cooldown_wait', 0):.0f}s"}
            return pkt, provider, "cooldown", use_id
        if status != "available" or not data:
            return dict(FALLBACK_PACKET), provider, "provider_error", use_id
        res_json = data
        text = ""
        for part in res_json.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            text += part.get("text", "")
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
        packet = json.loads(text)
        intent = (packet.get("intent") or "general_chat").strip().lower()
        if intent not in OPERATION_INTENTS:
            intent = "general_chat"
        packet["intent"] = intent
        try:
            packet["confidence"] = float(packet.get("confidence") or 0.0)
        except (TypeError, ValueError):
            packet["confidence"] = 0.0
        packet["extracted_fields"] = packet.get("extracted_fields") or {}
        packet["reason_short"] = packet.get("reason_short") or ""
        return packet, provider, "available", resolved_id
    except Exception as exc:
        logger.error("Operations classifier failed: %s", exc)
        return dict(FALLBACK_PACKET), provider, "provider_error", resolved_id


def deterministic_fallback_intent(message: str) -> dict | None:
    """M4-A8.5.2 — Natural-language routing removed; classifier must use model only."""
    del message
    return None


__all__ = [
    "classify_operations_intent",
    "deterministic_fallback_intent",
    "LOW_CONFIDENCE_THRESHOLD",
    "MEDIUM_CONFIDENCE_THRESHOLD",
    "OPERATION_INTENTS",
]

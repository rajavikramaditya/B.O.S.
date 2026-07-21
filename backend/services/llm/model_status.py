"""M4-A8.5 — Owner-safe model runtime status (no secrets)."""
from __future__ import annotations

import time
from typing import Any

import services.llm.provider_router as pr
from services.cockpit.job_service import list_active_jobs


def build_neena_model_status() -> dict[str, Any]:
    interpreter_id = pr.resolve_model_for_role("COMMAND_INTERPRETER_MODEL")
    creative_id = pr.resolve_model_for_role("CREATIVE_MODEL")
    fallback_id = pr.resolve_model_for_role("FALLBACK_MODEL")

    cooldown_active = False
    cooldown_remaining = 0.0
    for mid in filter(None, {interpreter_id, creative_id}):
        wait = pr.peek_cooldown_wait(mid)
        if wait > 0:
            cooldown_active = True
            cooldown_remaining = max(cooldown_remaining, wait)

    last_error = getattr(pr, "_LAST_MODEL_ERROR_SUMMARY", None) or None
    active_jobs = list_active_jobs(limit=20)
    model_jobs = [j for j in active_jobs if str(j.get("action", "")).startswith("creative_")]

    return {
        "ok": True,
        "interpreter_model": interpreter_id or "unavailable",
        "creative_model": creative_id or "unavailable",
        "fallback_model": fallback_id or "unavailable",
        "cooldown_active": cooldown_active,
        "cooldown_remaining_seconds": round(cooldown_remaining, 1),
        "rate_limit_detected": False,
        "last_error_summary": last_error,
        "model_job_queue_length": len(model_jobs),
        "dynamic_model_discovery_in_hot_path": False,
        "llm_configured": pr.is_llm_configured(),
        "model_list_status": pr.get_last_model_list_status(),
        "timestamp_ms": int(time.time() * 1000),
    }


def build_model_status_reply(snapshot: dict | None = None) -> str:
    """Hinglish owner reply from live model status + optional live snapshot."""
    st = build_neena_model_status()
    snap = snapshot or {}
    parts = [
        "Model status.",
        f"interpreter={st.get('interpreter_model')}",
        f"creative={st.get('creative_model')}",
        f"fallback={st.get('fallback_model')}",
        f"llm_configured={st.get('llm_configured')}",
        f"cooldown_active={st.get('cooldown_active')}",
        f"cooldown_remaining_seconds={st.get('cooldown_remaining_seconds')}",
    ]
    if st.get("last_error_summary"):
        parts.append(f"last_error={st['last_error_summary']}")
    rw = snap.get("resource_warning")
    if rw:
        parts.append(str(rw))
    parts.append("Local status/diagnostics/memory work without model.")
    return " ".join(parts)


__all__ = ["build_model_status_reply", "build_neena_model_status"]

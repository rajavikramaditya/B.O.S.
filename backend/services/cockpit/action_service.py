"""M4-A8.2-A/B + M4-A8.3 — Fast structured cockpit actions (no Gemini, background jobs)."""
from __future__ import annotations

import time
from typing import Any

from services.cockpit.status_fast import (
    format_diagnostics_fast_message,
    format_station_status_message,
    get_cockpit_status_snapshot_immediate,
)

COCKPIT_ACTIONS = frozenset(
    {
        "station_status",
        "diagnostics",
        "diagnostics_fast",
        "broadcast_readiness",
        "latest_verified_capsule",
        "verify_latest_stream",
    }
)

BACKGROUND_ACTIONS = frozenset({"verify_latest_stream"})


def _elapsed_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _action_station_status(t0: float) -> dict[str, Any]:
    snapshot = get_cockpit_status_snapshot_immediate()
    message = format_station_status_message(snapshot)
    return {
        "ok": True,
        "action": "station_status",
        "mode": "immediate",
        "message": message,
        "status": "station_status",
        "safe_details": {
            "health_tier": "fast_health",
            "stream_online": snapshot.get("stream_online"),
            "stream_status_cached": snapshot.get("stream_status_cached"),
            "stream_stale": snapshot.get("stream_stale"),
            "last_verified_capsule_id": snapshot.get("last_verified_capsule_id"),
        },
        "latency_ms": _elapsed_ms(t0),
        "gemini_calls": 0,
    }


def _action_diagnostics_fast(t0: float) -> dict[str, Any]:
    snapshot = get_cockpit_status_snapshot_immediate()
    message = format_diagnostics_fast_message(snapshot)
    return {
        "ok": True,
        "action": "diagnostics_fast",
        "mode": "immediate",
        "message": message,
        "status": "diagnostics_fast",
        "safe_details": {
            "health_tier": "fast_health",
            "degraded": snapshot.get("degraded_due_to_memory_stack_offline"),
        },
        "latency_ms": _elapsed_ms(t0),
        "gemini_calls": 0,
    }


def execute_cockpit_action(action: str, *, watch_seconds: int = 30) -> dict[str, Any]:
    """
    Run a structured cockpit action locally. Never calls Gemini or saves memory.
    Long actions should use dispatch_cockpit_action instead.
    """
    t0 = time.monotonic()
    action = (action or "").strip().lower()

    if action == "diagnostics":
        action = "diagnostics_fast"

    if action == "station_status":
        return _action_station_status(t0)

    if action == "diagnostics_fast":
        return _action_diagnostics_fast(t0)

    if action in BACKGROUND_ACTIONS:
        return {
            "ok": False,
            "action": action,
            "message": f"Action {action} must be dispatched as background job.",
            "status": "use_background",
            "latency_ms": _elapsed_ms(t0),
            "gemini_calls": 0,
        }

    if action not in COCKPIT_ACTIONS:
        return {
            "ok": False,
            "action": action,
            "message": f"Unknown cockpit action: {action}",
            "status": "invalid_action",
            "safe_details": {},
            "latency_ms": _elapsed_ms(t0),
            "gemini_calls": 0,
        }

    safe_details: dict[str, Any] = {}
    message = ""
    status = "ok"

    if action == "broadcast_readiness":
        from services.voice.gen_service import get_broadcast_audio_readiness

        readiness = get_broadcast_audio_readiness()
        safe_details = dict(readiness)
        tts = readiness.get("tts_status") or "unknown"
        can = readiness.get("can_produce_real_audio")
        message = (
            f"Broadcast readiness: TTS={tts}, real_audio={'yes' if can else 'no'}."
        )
        status = "broadcast_readiness"

    elif action == "latest_verified_capsule":
        from services.broadcast.capsule_service import list_recent_capsules

        capsules = list_recent_capsules(limit=10)
        verified = [
            c for c in capsules if c.get("stream_verification_status") == "verified"
        ]
        if verified:
            cap = verified[0]
            cid = cap.get("id")
            message = f"Latest verified capsule: #{cid}."
            safe_details["capsule_id"] = cid
            safe_details["verification_status"] = "verified"
        else:
            message = "Abhi koi stream-verified capsule nahi mila."
            safe_details["verification_status"] = "none"
        status = "latest_verified_capsule"

    return {
        "ok": True,
        "action": action,
        "mode": "immediate",
        "message": message,
        "status": status,
        "safe_details": safe_details,
        "latency_ms": _elapsed_ms(t0),
        "gemini_calls": 0,
    }


def dispatch_cockpit_action(action: str, *, watch_seconds: int = 30) -> dict[str, Any]:
    """Route immediate vs background cockpit actions."""
    action = (action or "").strip().lower()
    if action == "diagnostics":
        action = "diagnostics_fast"

    if action in BACKGROUND_ACTIONS:
        from services.cockpit.job_service import submit_background_job

        payload: dict[str, Any] = {}
        if action == "verify_latest_stream":
            payload["watch_seconds"] = max(0, min(int(watch_seconds or 0), 60))
        return submit_background_job(action, payload)

    result = execute_cockpit_action(action, watch_seconds=watch_seconds)
    if "mode" not in result:
        result["mode"] = "immediate"
    return result


def execute_cockpit_action_for_chat(action: str, slots: dict | None = None) -> dict[str, Any]:
    """Chat-side local execution after interpreter (no Gemini)."""
    slots = slots or {}
    watch = int(slots.get("watch_seconds") or 30)
    if action == "station_status":
        t0 = time.monotonic()
        snapshot = get_cockpit_status_snapshot_immediate()
        message = format_station_status_message(snapshot)
        return {
            "reply": message,
            "action_type": "STATION_STATUS",
            "latency_ms": _elapsed_ms(t0),
            "gemini_calls": 0,
        }
    if action == "diagnostics":
        t0 = time.monotonic()
        res = execute_cockpit_action("diagnostics_fast")
        return {
            "reply": res["message"],
            "action_type": "RUN_DIAGNOSTICS",
            "command_triggered": "RUN_DIAGNOSTICS",
            "latency_ms": _elapsed_ms(t0),
            "gemini_calls": 0,
        }
    if action == "broadcast_readiness":
        res = execute_cockpit_action("broadcast_readiness")
        return {
            "reply": res["message"],
            "action_type": "BROADCAST_READINESS",
            "latency_ms": res["latency_ms"],
            "gemini_calls": 0,
        }
    if action == "verify_stream":
        res = dispatch_cockpit_action("verify_latest_stream", watch_seconds=watch)
        return {
            "reply": res.get("message") or "Stream verification queued.",
            "action_type": "STREAM_VERIFY",
            "job_id": res.get("job_id"),
            "latency_ms": res.get("latency_ms", 0),
            "gemini_calls": 0,
        }
    return {}


__all__ = [
    "BACKGROUND_ACTIONS",
    "COCKPIT_ACTIONS",
    "dispatch_cockpit_action",
    "execute_cockpit_action",
    "execute_cockpit_action_for_chat",
]

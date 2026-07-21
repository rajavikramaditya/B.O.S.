"""Local live-ops fast path (explicit action_id only, no NL routing). ADR-013: tools/."""
from __future__ import annotations

from services.brain.command_execution_kernel import (
    CREATIVE_KERNEL_ACTIONS,
    KERNEL_LOCAL_ACTIONS,
    normalize_action_key,
)
from services.brain.live_state_snapshot import build_neena_live_state_snapshot
from services.brain.load_shedding import build_load_defer_payload, is_load_high
from services.tools.live_ops_executor import try_execute_live_ops

LOCAL_FAST_ACTIONS = frozenset(
    KERNEL_LOCAL_ACTIONS
    | {
        "verify_stream",
        "approve_latest_script",
        "generate_audio",
        "send_azuracast",
        "ensure_playback",
    }
)


def _enqueue_creative_quick(message: str, action: str, slots: dict) -> dict:
    from services.brain.creative_jobs import enqueue_creative_command_job

    snap = build_neena_live_state_snapshot()
    if is_load_high(snap, 85.0):
        out = build_load_defer_payload(snap)
        out["handled"] = True
        return out
    packet = {
        "action": action,
        "confidence": 1.0,
        "slots": dict(slots or {}),
        "needs_confirmation": False,
    }
    job = enqueue_creative_command_job(message, packet, "auto")
    return {
        "handled": True,
        "reply": job.get("message")
        or (
            f"Creative job queued. action={action}. "
            f"job_id={job.get('job_id')}. Result will push when complete."
        ),
        "action_type": "CREATIVE_BACKGROUND",
        "job_id": job.get("job_id"),
        "mode": "background",
        "gemini_calls": 0,
        "ui_action": {
            "type": "poll_cockpit_job",
            "job_id": job.get("job_id"),
            "action_key": "creative_job",
        },
    }


def try_live_ops_quick(*, message: str = "", action: str = "", slots: dict | None = None) -> dict | None:
    """
    Run local live-ops for an explicit structured action_id (dashboard buttons / API action param).
    Natural-language owner text must not be routed here — use model interpreter + executor instead.
    """
    action_key = normalize_action_key(action)
    slot_data = dict(slots or {})
    msg = (message or "").strip()

    if not action_key:
        return None

    if action_key in CREATIVE_KERNEL_ACTIONS:
        return _enqueue_creative_quick(msg, action_key, slot_data)

    if action_key not in LOCAL_FAST_ACTIONS:
        return None

    if action_key in ("station_status", "diagnostics"):
        from services.cockpit.action_service import execute_cockpit_action_for_chat

        local = execute_cockpit_action_for_chat(action_key, slot_data)
        if not local:
            return None
        local["handled"] = True
        snap = build_neena_live_state_snapshot()
        local["live_snapshot"] = {
            "recommended_next_action": snap.get("recommended_next_action"),
            "pending_scripts_count": snap.get("pending_scripts_count"),
            "resource_warning": snap.get("resource_warning"),
        }
        return local

    snap = build_neena_live_state_snapshot()
    live = try_execute_live_ops(action_key, slot_data, snapshot=snap, owner_message=msg)
    if not live:
        return None
    live["handled"] = True
    live["live_snapshot"] = {
        "recommended_next_action": snap.get("recommended_next_action"),
        "pending_scripts_count": snap.get("pending_scripts_count"),
        "resource_warning": snap.get("resource_warning"),
    }
    return live


__all__ = ["LOCAL_FAST_ACTIONS", "try_live_ops_quick"]

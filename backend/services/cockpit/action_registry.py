"""M4-A8.4 — Command Center action registry (live enabled/blocked state + voice templates)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Static action definitions; `current_enabled` / `blocked_reason` filled from live snapshot.
ACTION_REGISTRY_TEMPLATE: list[dict[str, Any]] = [
    {
        "action_id": "station_status",
        "display_name": "Status",
        "category": "cockpit_pill",
        "requires_confirmation": False,
        "endpoint": "POST /api/neena/cockpit-action",
        "payload": {"action": "station_status"},
        "expected_result": "Cached station health summary",
        "voice_start": "Station status check kar rahi hoon.",
        "voice_success": "Status ready hai.",
        "voice_failure": "Status abhi fetch nahi ho paya.",
    },
    {
        "action_id": "diagnostics_fast",
        "display_name": "Diagnostics",
        "category": "cockpit_pill",
        "requires_confirmation": False,
        "endpoint": "POST /api/neena/cockpit-action",
        "payload": {"action": "diagnostics_fast"},
        "expected_result": "Fast diagnostics report",
        "voice_start": "Fast diagnostics chala rahi hoon.",
        "voice_success": "Diagnostics ready.",
        "voice_failure": "Diagnostics fail ho gaye.",
    },
    {
        "action_id": "verify_latest_stream",
        "display_name": "Verify Stream",
        "category": "cockpit_pill",
        "requires_confirmation": False,
        "endpoint": "POST /api/neena/cockpit-action",
        "payload": {"action": "verify_latest_stream"},
        "expected_result": "Background stream verification job",
        "voice_start": "Stream verification start kar di hai.",
        "voice_success": "Stream verified hai.",
        "voice_failure": "Stream abhi play nahi ho rahi.",
    },
    {
        "action_id": "what_should_i_do_now",
        "display_name": "What should I do now?",
        "category": "live_ops",
        "requires_confirmation": False,
        "endpoint": "internal://live-recommendation",
        "expected_result": "Live next-step guidance from snapshot",
        "voice_start": "Abhi ka live state dekh rahi hoon.",
        "voice_success": "Next step suggest kar diya.",
        "voice_failure": "Live state abhi read nahi ho paya.",
    },
    {
        "action_id": "open_latest_script",
        "display_name": "Open Latest Script",
        "category": "live_ops",
        "requires_confirmation": False,
        "endpoint": "ui://open-latest-script",
        "expected_result": "Neena Lab / pipeline shows latest pending script",
        "voice_start": "Latest script khol rahi hoon.",
        "voice_success": "Latest script khol di hai. Review karke approve kar sakte hain.",
        "voice_failure": "Koi pending script nahi mila.",
    },
    {
        "action_id": "approve_latest_script",
        "display_name": "Approve Latest Script",
        "category": "live_ops",
        "requires_confirmation": True,
        "endpoint": "POST /api/admin/approval-queue/{id}/action",
        "expected_result": "Latest pending script approved (no auto-broadcast)",
        "voice_start": "Latest pending script approve kar rahi hoon.",
        "voice_success": "Capsule approve kar diya. Ab audio generate karna next step hai.",
        "voice_failure": "Approve nahi ho paya.",
    },
    {
        "action_id": "generate_audio_latest",
        "display_name": "Generate Audio (latest approved)",
        "category": "capsule_pipeline",
        "requires_confirmation": False,
        "endpoint": "POST /api/broadcast/capsules/{id}/generate-audio",
        "expected_result": "Real/simulated audio for approved capsule",
        "voice_start": "Audio generate kar rahi hoon.",
        "voice_success": "Audio generate ho gaya.",
        "voice_failure": "Audio generate nahi ho paya.",
    },
    {
        "action_id": "send_azuracast_latest",
        "display_name": "Send to AzuraCast",
        "category": "capsule_pipeline",
        "requires_confirmation": True,
        "endpoint": "POST /api/broadcast/capsules/{id}/send-azuracast",
        "expected_result": "Capsule uploaded to AzuraCast (owner-approved only)",
        "voice_start": "AzuraCast upload start kar rahi hoon.",
        "voice_success": "AzuraCast upload complete.",
        "voice_failure": "AzuraCast upload fail.",
    },
    {
        "action_id": "explain_button",
        "display_name": "Explain Button",
        "category": "live_ops",
        "requires_confirmation": False,
        "endpoint": "internal://explain-button",
        "expected_result": "Button purpose using current capsule/state",
        "voice_start": "Is button ka matlab live state ke hisaab se bata rahi hoon.",
        "voice_success": "Button explain kar diya.",
        "voice_failure": "Button samajh nahi aaya.",
    },
    {
        "action_id": "pipeline_approve",
        "display_name": "Approve",
        "category": "capsule_pipeline",
        "requires_confirmation": True,
        "endpoint": "POST /api/admin/approval-queue/{id}/action",
        "expected_result": "Moves script to next broadcast pipeline step",
        "voice_start": "Script approve kar rahi hoon.",
        "voice_success": "Approve ho gaya.",
        "voice_failure": "Approve blocked.",
    },
    {
        "action_id": "pipeline_audio",
        "display_name": "Audio",
        "category": "capsule_pipeline",
        "requires_confirmation": False,
        "endpoint": "POST /api/broadcast/capsules/{id}/generate-audio",
        "expected_result": "Generate capsule audio after approval",
        "voice_start": "Capsule audio generate kar rahi hoon.",
        "voice_success": "Audio ready.",
        "voice_failure": "Audio blocked.",
    },
    {
        "action_id": "pipeline_azuracast",
        "display_name": "AzuraCast",
        "category": "capsule_pipeline",
        "requires_confirmation": True,
        "endpoint": "POST /api/broadcast/capsules/{id}/send-azuracast",
        "expected_result": "Upload approved real audio to AzuraCast",
        "voice_start": "AzuraCast push kar rahi hoon.",
        "voice_success": "Upload ho gaya.",
        "voice_failure": "Upload blocked.",
    },
]


def _capsule_summary(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "title": c.get("title"),
        "capsule_type": c.get("capsule_type"),
        "approval_status": c.get("approval_status"),
        "approval_queue_id": c.get("approval_queue_id"),
        "audio_truth_level": c.get("audio_truth_level"),
        "azuracast_status": c.get("azuracast_status"),
        "stream_verification_status": c.get("stream_verification_status"),
        "azuracast_push_allowed": c.get("azuracast_push_allowed"),
        "azuracast_push_block_reason": c.get("azuracast_push_block_reason"),
    }


def build_action_registry(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge template actions with live enabled/blocked state."""
    registry = deepcopy(ACTION_REGISTRY_TEMPLATE)
    pending = snapshot.get("pending_scripts") or []
    latest_pending = snapshot.get("latest_pending_capsule")
    latest_approved_no_audio = snapshot.get("latest_approved_needs_audio")
    latest_ready_azura = snapshot.get("latest_ready_for_azuracast")
    auth_locked = snapshot.get("auth") == "locked"
    tts_ready = snapshot.get("tts") in ("real", "simulated")
    az_ready = snapshot.get("azuracast") == "ready"

    def set_state(entry: dict, enabled: bool, reason: str | None = None) -> None:
        entry["current_enabled"] = enabled
        entry["blocked_reason"] = None if enabled else (reason or "blocked")

    for entry in registry:
        aid = entry["action_id"]
        if auth_locked and aid not in ("station_status", "diagnostics_fast", "what_should_i_do_now"):
            set_state(entry, False, "Command Center locked — admin token required")
            continue

        if aid in ("station_status", "diagnostics_fast", "what_should_i_do_now", "explain_button"):
            set_state(entry, True)
        elif aid == "verify_latest_stream":
            set_state(entry, bool(snapshot.get("latest_capsules")), "Koi capsule nahi — pehle script banao")
        elif aid == "open_latest_script":
            set_state(entry, bool(pending or snapshot.get("latest_capsules")), "Koi script/capsule nahi mila")
        elif aid in ("approve_latest_script", "pipeline_approve"):
            if latest_pending:
                set_state(entry, True)
                entry["target_approval_id"] = latest_pending.get("approval_queue_id")
                entry["target_capsule_id"] = latest_pending.get("id")
            else:
                set_state(entry, False, "Koi pending script approval nahi hai")
        elif aid in ("generate_audio_latest", "pipeline_audio"):
            cap = latest_approved_no_audio or latest_pending
            if cap and cap.get("approval_status") == "approved" and cap.get("audio_truth_level") in (None, "none"):
                set_state(entry, tts_ready, "TTS provider not ready" if not tts_ready else None)
                entry["target_capsule_id"] = cap.get("id")
            elif latest_pending and latest_pending.get("approval_status") != "approved":
                set_state(entry, False, "Pehle script approve karni hogi")
            else:
                set_state(entry, False, "Approved capsule jisme audio chahiye — nahi mila")
        elif aid in ("send_azuracast_latest", "pipeline_azuracast"):
            cap = latest_ready_azura
            if cap and cap.get("azuracast_push_allowed"):
                set_state(entry, True)
                entry["target_capsule_id"] = cap.get("id")
            elif cap:
                set_state(entry, False, cap.get("azuracast_push_block_reason") or "AzuraCast push blocked")
            else:
                set_state(entry, False, "Real audio + approval ke baad hi AzuraCast push hoga")
        else:
            set_state(entry, True)

        if aid == "pipeline_azuracast" and not az_ready:
            set_state(entry, False, "AzuraCast config not ready")

    return registry


def registry_to_public_map(registry: list[dict]) -> dict[str, Any]:
    enabled = [a["action_id"] for a in registry if a.get("current_enabled")]
    blocked = [
        {"action_id": a["action_id"], "blocked_reason": a.get("blocked_reason")}
        for a in registry
        if not a.get("current_enabled")
    ]
    return {
        "actions": registry,
        "available_actions": enabled,
        "blocked_actions": blocked,
    }


__all__ = [
    "ACTION_REGISTRY_TEMPLATE",
    "build_action_registry",
    "registry_to_public_map",
]

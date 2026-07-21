"""M0 foundation Safety Kernel for Orai Radio Neena system."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Safety constants
PROTECTED_ACTIONS: frozenset[str] = frozenset({
    "vm_restart",
    "deployment",
    ".env_edit",
    "db_schema_change",
    "mobile_app_changes",
    "arbitrary_shell",
    "live_ops_restart",
    "stream_server_restart",
    "production_broadcast_changes",
    "send_azuracast",
})

BROADCAST_PROTECTED_PATTERNS: tuple[str, ...] = (
    "broadcast now",
    "broadcast karo",
    "abhi broadcast karo",
    "send to azuracast",
    "azuracast par bhejo",
    "azuracast pe bhejo",
    "azuracast me bhejo",
    "azuracast mein bhejo",
    "radio par chalao",
    "radio pe chalao",
    "radio par chala do",
    "radio pe chala do",
    "station par chalao",
    "station pe chalao",
    "station par chala do",
    "station pe chala do",
    "live kar do",
    "live karo",
    "on air kar do",
    "on air karo",
    "isko chala do",
    "latest chala do",
    "approved capsule chala do",
    "air karo",
    "on air karo",
    "chala do",
    "play it",
    "abhi chala do",
    "station pe bhejo",
    "broadcast kar do",
    "radio pe bhejo",
)

EXPLICIT_AUDIO_INTENTS: tuple[str, ...] = (
    "audio banao",
    "audio bana do",
    "voice banao",
    "voice preview banao",
    "prepare audio",
    "tts banao",
    "voice generate karo",
    "capsule audio",
    "audio tayar karo",
    "sound generate karo",
)

ALLOWED_BROADCAST_READY_STATUSES: frozenset[str] = frozenset({
    "ready_for_broadcast",
    "approved_for_broadcast",
})


def classify_owner_command_safety(message: str, proposed_action: str) -> dict[str, any]:
    """Safety reclassification post-LLM or pre-execution."""
    msg_lower = (message or "").lower().strip()
    action = proposed_action
    reclassified = False
    original_action = proposed_action
    reason = None

    # Rule 1: Broadcast patterns always map to send_azuracast
    for pattern in BROADCAST_PROTECTED_PATTERNS:
        if pattern in msg_lower:
            if action != "send_azuracast":
                logger.warning(
                    "[SAFETY_KERNEL] Broadcast pattern '%s' matched in '%s' — overriding action '%s' -> send_azuracast",
                    pattern, msg_lower[:80], action
                )
                action = "send_azuracast"
                reclassified = True
                reason = f"broadcast_pattern_match:{pattern}"
            return {
                "action": action,
                "reclassified": reclassified,
                "original_action": original_action,
                "reason": reason,
            }

    # Rule 2: generate_audio requires explicit audio intent
    if action in ("generate_audio", "prepare_capsule_audio"):
        has_explicit = any(intent in msg_lower for intent in EXPLICIT_AUDIO_INTENTS)
        if not has_explicit:
            logger.warning(
                "[SAFETY_KERNEL] generate_audio routed without explicit audio intent in '%s' — overriding to unknown",
                msg_lower[:80]
            )
            action = "unknown"
            reclassified = True
            reason = "no_explicit_audio_intent"

    return {
        "action": action,
        "reclassified": reclassified,
        "original_action": original_action,
        "reason": reason,
    }


def is_broadcast_ready(audio_truth_level: str | None, db_broadcast_ready: int | bool, azuracast_status: str | None) -> bool:
    """Computed tri-gate safety check for capsule broadcast readiness."""
    is_real = audio_truth_level == "real"
    db_ok = bool(db_broadcast_ready)
    status_ok = (azuracast_status or "blocked") in ALLOWED_BROADCAST_READY_STATUSES
    return is_real and db_ok and status_ok


def requires_owner_confirmation(action: str) -> bool:
    """Returns True if the proposed action is protected and needs owner confirmation."""
    return action in PROTECTED_ACTIONS or action in ("approve_latest_script", "approve_capsule")


def can_call_real_tts(message: str, action: str, capsule_status: str | None) -> bool:
    """TTS execution gate."""
    msg_lower = (message or "").lower().strip()
    if action not in ("generate_audio", "prepare_capsule_audio"):
        return False
    if capsule_status not in ("approved", "audio_pending", "audio_ready_preview"):
        return False
    # Must have an explicit audio intent pattern in natural language
    return any(intent in msg_lower for intent in EXPLICIT_AUDIO_INTENTS)


def can_push_azuracast(capsule: dict) -> bool:
    """AzuraCast push readiness validator."""
    status = capsule.get("status")
    is_real = capsule.get("audio_truth_level") == "real"
    playable = capsule.get("audio_playable")

    return (
        status in ("approved", "audio_ready_preview")
        and is_real
        and bool(playable)
    )

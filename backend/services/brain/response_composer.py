import json
import re
from typing import Any

# Informational report actions — always eligible for humanize (gated by NEENA_SMART_REPLY).
_REPORT_HUMANIZE_ACTION_TYPES = frozenset({
    "STATION_STATUS",
    "RUN_DIAGNOSTICS",
    "MODEL_STATUS",
    "MEMORY_STATUS",
    "VM_STATUS",
    "CAPSULE_STATUS",
    "CAPSULE_STATUS_NONE",
    "RECORDER_CHECK",
    "RECORDER_CHECK_DISABLED",
    # Memory / self-notebook — deterministic facts; conversation LLM composes owner Hinglish
    "PERMANENT_MEMORY_SAVED",
    "PERMANENT_MEMORY_CANDIDATE",
    "PERMANENT_MEMORY_CANCEL",
    "PERMANENT_MEMORY_RETRIEVAL",
    "PROPOSE_PERMANENT_MEMORY",
    "MANAGE_MEMORY",
    "MEMORY_EDIT_APPLIED",
    "MEMORY_EDIT_CANCEL",
    "SET_RESPONSE_STYLE",
    "SELF_PROFILE",
    "SELF_LIFE_STORY",
    "SELF_ARCHITECTURE",
    "SELF_LIFE_MILESTONE",
    "DAY_MEMORY_RECALL",
    "FUTURE_INTENTION_SAVED",
    "FUTURE_INTENTION_RECALL",
    "FUTURE_INTENTION_NEEDS_CONTENT",
    "FUTURE_INTENTION_BLOCKED",
    "FUTURE_INTENTION_COMPLETE",
    "FUTURE_INTENTION_CANCEL",
    "FUTURE_INTENTION_POSTPONE",
    "TIME_STATUS",
    "SELF_CHANGE_ANNOUNCE",
    "SELF_CHANGE_STATUS",
    # Honesty / recall — factual fallback must still sound human when LLM available
    "CUSTOMER_WHATSAPP_RECALL",
    "CANNOT",
})

# Live-ops outcomes converted to factual packets. Extra gate: NEENA_HUMANIZE_LIVE_OPS.
_LIVE_OPS_HUMANIZE_ACTION_TYPES = frozenset({
    # Phase 2 pilot
    "DIAGNOSE_LISTENER_PATH",
    "LISTENER_PATH_DISABLED",
    "FIX_APP_LISTENER_PATH",
    "FIX_APP_LISTENER_PATH_CONFIRM",
    "FIX_APP_LISTENER_PATH_BLOCKED",
    "FIX_APP_LISTENER_PATH_FAILED",
    "LIST_PENDING_CAPSULES",
    "APPROVE_MULTIPLE",
    "APPROVE_NONE",
    "APPROVE_ALREADY_DONE",
    "APPROVE_BLOCKED",
    "APPROVE_CONFIRM",
    "APPROVE_CAPSULE",
    "APPROVE_LATEST",
    "APPROVE_FAILED",
    "SEND_AZURACAST",
    "SEND_AZURACAST_CONFIRM",
    "SEND_AZURACAST_BLOCKED",
    "SEND_AZURACAST_FAILED",
    # Phase 3
    "GENERATE_AUDIO",
    "GENERATE_AUDIO_BLOCKED",
    "GENERATE_AUDIO_FAILED",
    "GENERATE_AUDIO_ERROR",
    "REJECT_MULTIPLE",
    "REJECT_NONE",
    "REJECT_ALREADY_DONE",
    "REJECT_BLOCKED",
    "REJECT_CAPSULE",
    "REJECT_FAILED",
    "REVISION_MULTIPLE",
    "REVISION_NONE",
    "REVISION_ALREADY_DONE",
    "NEEDS_REVISION",
    "REVISION_FAILED",
    "OPEN_SCRIPT_NONE",
    "OPEN_LATEST_SCRIPT",
    "OPEN_LATEST_CAPSULE",
    "PIPELINE_STATUS",
    "TIMEOUT_DIAGNOSIS",
    "STREAM_VERIFY",
    "ENSURE_PLAYBACK",
    "ENSURE_PLAYBACK_BLOCKED",
    # Phase 4
    "EXPLAIN_BUTTON",
    "CAPABILITIES",
    "AUTH_SESSION_EXPLAIN",
    "ADMIN_LOCK",
    "LIVE_RECOMMENDATION",
    "CAPSULE_STATUS_CLARIFY",
})

# Back-compat alias used by tests
_HUMANIZE_ACTION_TYPES = _REPORT_HUMANIZE_ACTION_TYPES | _LIVE_OPS_HUMANIZE_ACTION_TYPES


def maybe_humanize_report(
    message,
    reply,
    action_type,
    *,
    concise: bool = False,
    factual_packet: dict[str, Any] | None = None,
) -> str:
    """Rephrase factual DATA into human Hinglish (best-effort, fail-closed).

    Prefer structured factual_packet when present. Returns the short factual
    reply unchanged when not allowlisted, live-ops flag off, or LLM unavailable.
    """
    if isinstance(factual_packet, dict) and factual_packet.get("tool") == "agent_loop":
        # Multi-step turns already synthesized in neena_tool_loop — do not rephrase again.
        if int(factual_packet.get("step_count") or 0) > 1:
            return reply

    is_report = action_type in _REPORT_HUMANIZE_ACTION_TYPES
    is_live_ops = action_type in _LIVE_OPS_HUMANIZE_ACTION_TYPES
    if not is_report and not is_live_ops:
        return reply

    if is_live_ops and not is_report:
        try:
            import services.brain.feature_flags as feature_flags

            if not feature_flags.humanize_live_ops_enabled():
                return reply
        except Exception:
            return reply

    factual_text = reply
    if factual_packet is not None:
        try:
            factual_text = json.dumps(factual_packet, ensure_ascii=False, default=str)
        except Exception:
            factual_text = reply

    try:
        from services.brain.conversation import humanize_factual_reply

        humanized = humanize_factual_reply(
            factual_text=factual_text, message=message, concise=concise
        )
        return humanized or reply
    except Exception:
        return reply


def compose_response(llm_output: str) -> str:
    """
    Ensures final responses adhere to the standard script output format,
    strips conversational fillers, and enforces a maximum character limit.
    """
    text = llm_output.strip()

    # 1. Clean conversational LLM prefixes / fillers (case-insensitive)
    pattern = r"^(certainly|of course|sure|absolutely|as an ai (language model|assistant)?)[!.,]?\s*"

    old_text = None
    while old_text != text:
        old_text = text
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # 2. Validation: If the LLM forgot to close a tag, auto-close it
    if "[SCRIPT_OUTPUT]" in text and "[/SCRIPT_OUTPUT]" not in text:
        text += "\n[/SCRIPT_OUTPUT]"

    # Scripts must not be hard-cut at ~200 words. Soft cap only for huge dumps.
    _MAX = 16000
    if len(text) > _MAX:
        truncated = text[: _MAX - 20]
        last_space = truncated.rfind(" ")
        text = (truncated[:last_space] if last_space > _MAX // 2 else truncated) + "..."
        if "[SCRIPT_OUTPUT]" in text and "[/SCRIPT_OUTPUT]" not in text:
            text = text.rstrip(".") + "\n[/SCRIPT_OUTPUT]"

    return text

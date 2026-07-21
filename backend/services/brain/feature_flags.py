"""Runtime feature flags for Neena intelligence upgrades.

Every new behavior is gated here so it can be toggled via environment
variables WITHOUT a redeploy. Defaults are chosen to enable the upgrades
while keeping a safe fallback path in code (if a flag is turned off, Neena
reverts to the previous deterministic behavior).

Phase 4 CC settings can set Redis/process overrides for a small allowlist
(kill switches without editing .env). Env remains the default when no override.
"""
from __future__ import annotations

import os
from typing import Any

# Process-local mirror of Redis overrides (same worker continuity).
_OVERRIDES: dict[str, bool] = {}
_OVERRIDES_LOADED = False

# Flags the Command Center Settings UI may toggle at runtime.
CC_TOGGLEABLE_FLAGS: tuple[str, ...] = (
    "NEENA_OWNER_WORKING_CONTEXT",
    "NEENA_SYSTEM_KNOWLEDGE_PACK",
    "NEENA_BOUNDED_TOOL_LOOP",
    "NEENA_DEEP_AGENT_LOOP",
)


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _load_overrides() -> dict[str, bool]:
    global _OVERRIDES_LOADED
    if _OVERRIDES_LOADED:
        return dict(_OVERRIDES)
    try:
        import services.brain.redis_state as redis_state

        got = redis_state.get_feature_flag_overrides()
        data = got.get("overrides") if got.get("success") else None
        if isinstance(data, dict):
            for k, v in data.items():
                if k in CC_TOGGLEABLE_FLAGS and isinstance(v, bool):
                    _OVERRIDES[k] = v
    except Exception:
        pass
    _OVERRIDES_LOADED = True
    return dict(_OVERRIDES)


def _flag(name: str, default: bool = True) -> bool:
    overrides = _load_overrides()
    if name in overrides:
        return bool(overrides[name])
    return _parse_bool(os.environ.get(name), default)


def smart_reply_enabled() -> bool:
    """Natural LLM conversational reply layer (Gemma-first)."""
    return _flag("NEENA_SMART_REPLY", True)


def conversation_memory_enabled() -> bool:
    """Inject recent conversation turns into the reply prompt."""
    return _flag("NEENA_CONV_MEMORY", True)


def job_followup_enabled() -> bool:
    """Server-side delivery of finished background-job results."""
    return _flag("NEENA_JOB_FOLLOWUP", True)


def job_whatsapp_push_enabled() -> bool:
    """Push finished long-job results to the owner on WhatsApp."""
    return _flag("NEENA_JOB_WHATSAPP_PUSH", True)


def customer_brain_enabled() -> bool:
    """Env flag NEENA_CUSTOMER_BRAIN — gates customer WhatsApp *chat path* (not a 2nd brain)."""
    return _flag("NEENA_CUSTOMER_BRAIN", True)


def owner_customer_context_enabled() -> bool:
    """Owner can ask about customer WhatsApp threads (read-only Redis/recorder)."""
    return _flag("NEENA_OWNER_CUSTOMER_CONTEXT", True)


def listener_path_tools_enabled() -> bool:
    """Diagnose frozen-app listener path + remote app_config URL switch."""
    return _flag("NEENA_LISTENER_PATH_TOOLS", True)


def recorder_self_check_enabled() -> bool:
    """Owner can ask Neena to read-only review recent interaction recorder turns."""
    return _flag("NEENA_RECORDER_SELF_CHECK", True)


def humanize_live_ops_enabled() -> bool:
    """LLM-compose owner replies for live-ops factual packets (kill switch)."""
    return _flag("NEENA_HUMANIZE_LIVE_OPS", True)


def one_brain_foundation_enabled() -> bool:
    """Shared memory facade + CC via router + actor-scoped recall (kill switch)."""
    return _flag("NEENA_ONE_BRAIN_FOUNDATION", True)


def customer_salient_memory_enabled() -> bool:
    """Auto-save salient/repeated customer facts (1B) into durable memory."""
    return _flag("NEENA_CUSTOMER_SALIENT_MEMORY", True)


def memory_soft_fade_enabled() -> bool:
    """Soft-fade unused memories in retrieval scoring (2A); never hard-delete."""
    return _flag("NEENA_MEMORY_SOFT_FADE", True)


def owner_working_context_enabled() -> bool:
    """Owner Redis/in-process short-term working scratchpad (Cursor-like)."""
    return _flag("NEENA_OWNER_WORKING_CONTEXT", True)


def system_knowledge_pack_enabled() -> bool:
    """Inject lean runtime system knowledge pack into owner prompts."""
    return _flag("NEENA_SYSTEM_KNOWLEDGE_PACK", True)


def station_plan_enabled() -> bool:
    """Living Station Clock plan hands (not capsule show-plan)."""
    return _flag("NEENA_STATION_PLAN", True)


def bounded_tool_loop_enabled() -> bool:
    """Allow 2–3 safe follow-up tools in one owner turn (Phase 3)."""
    return _flag("NEENA_BOUNDED_TOOL_LOOP", True)


def deep_agent_loop_enabled() -> bool:
    """Phase 5: deeper mini-plan + up to 5 safe read-only follow-ups."""
    return _flag("NEENA_DEEP_AGENT_LOOP", False)


def self_change_awareness_enabled() -> bool:
    """Feel tool/flag/architecture inventory diffs across restarts (ADR-010)."""
    return _flag("NEENA_SELF_CHANGE_AWARENESS", True)


def self_heal_enabled() -> bool:
    """Emergency self-heal ladder from resource_monitor (ADR-011). Default off until host agent live."""
    return _flag("NEENA_SELF_HEAL", False)


def self_heal_reboot_allowed() -> bool:
    """Allow last-resort host reboot step. Requires NEENA_SELF_HEAL=1 too."""
    return _flag("NEENA_SELF_HEAL_ALLOW_REBOOT", False)


def self_heal_dry_run() -> bool:
    """Log heal requests without writing host request file."""
    return _flag("NEENA_SELF_HEAL_DRY_RUN", False)


def snapshot_agent_flags() -> dict[str, Any]:
    """Public snapshot for CC Settings (no secrets)."""
    overrides = _load_overrides()
    flags = {
        "NEENA_OWNER_WORKING_CONTEXT": {
            "enabled": owner_working_context_enabled(),
            "env_default": _parse_bool(os.environ.get("NEENA_OWNER_WORKING_CONTEXT"), True),
            "override": overrides.get("NEENA_OWNER_WORKING_CONTEXT"),
            "toggleable": True,
            "label": "Owner working context",
            "description": "Short-term scratchpad for follow-ups (Result?, usi id).",
        },
        "NEENA_SYSTEM_KNOWLEDGE_PACK": {
            "enabled": system_knowledge_pack_enabled(),
            "env_default": _parse_bool(os.environ.get("NEENA_SYSTEM_KNOWLEDGE_PACK"), True),
            "override": overrides.get("NEENA_SYSTEM_KNOWLEDGE_PACK"),
            "toggleable": True,
            "label": "System knowledge pack",
            "description": "Lean runtime rules (confirm / customer boundaries).",
        },
        "NEENA_BOUNDED_TOOL_LOOP": {
            "enabled": bounded_tool_loop_enabled(),
            "env_default": _parse_bool(os.environ.get("NEENA_BOUNDED_TOOL_LOOP"), True),
            "override": overrides.get("NEENA_BOUNDED_TOOL_LOOP"),
            "toggleable": True,
            "label": "Bounded tool loop",
            "description": "2–3 safe follow-up tools in one turn; protected still confirm.",
        },
        "NEENA_DEEP_AGENT_LOOP": {
            "enabled": deep_agent_loop_enabled(),
            "env_default": _parse_bool(os.environ.get("NEENA_DEEP_AGENT_LOOP"), False),
            "override": overrides.get("NEENA_DEEP_AGENT_LOOP"),
            "toggleable": True,
            "label": "Deep agent loop",
            "description": "Diagnose mini-plan + up to 5 read-only explores; writes still confirm.",
        },
    }
    return {"ok": True, "flags": flags, "toggleable": list(CC_TOGGLEABLE_FLAGS)}


def set_flag_override(name: str, enabled: bool | None) -> dict[str, Any]:
    """Set or clear a CC toggleable override. enabled=None clears override (env wins)."""
    global _OVERRIDES_LOADED
    key = (name or "").strip().upper()
    if key not in CC_TOGGLEABLE_FLAGS:
        return {"ok": False, "error": "flag_not_toggleable", "flag": key}

    _load_overrides()
    if enabled is None:
        _OVERRIDES.pop(key, None)
    else:
        _OVERRIDES[key] = bool(enabled)
    _OVERRIDES_LOADED = True

    try:
        import services.brain.redis_state as redis_state

        redis_state.save_feature_flag_overrides(dict(_OVERRIDES))
    except Exception:
        pass

    return {"ok": True, **snapshot_agent_flags()}


def clear_all_flag_overrides() -> dict[str, Any]:
    global _OVERRIDES_LOADED
    _OVERRIDES.clear()
    _OVERRIDES_LOADED = True
    try:
        import services.brain.redis_state as redis_state

        redis_state.save_feature_flag_overrides({})
    except Exception:
        pass
    return snapshot_agent_flags()


__all__ = [
    "CC_TOGGLEABLE_FLAGS",
    "smart_reply_enabled",
    "conversation_memory_enabled",
    "job_followup_enabled",
    "job_whatsapp_push_enabled",
    "customer_brain_enabled",
    "owner_customer_context_enabled",
    "listener_path_tools_enabled",
    "recorder_self_check_enabled",
    "humanize_live_ops_enabled",
    "one_brain_foundation_enabled",
    "customer_salient_memory_enabled",
    "memory_soft_fade_enabled",
    "owner_working_context_enabled",
    "system_knowledge_pack_enabled",
    "station_plan_enabled",
    "bounded_tool_loop_enabled",
    "deep_agent_loop_enabled",
    "self_change_awareness_enabled",
    "self_heal_enabled",
    "self_heal_reboot_allowed",
    "self_heal_dry_run",
    "snapshot_agent_flags",
    "set_flag_override",
    "clear_all_flag_overrides",
]

import time
import uuid
import json
from datetime import datetime

import services.brain.redis_state as redis_state

# In-memory runtime session state (local fallback mirror)
_state = {
    "last_intent": None,
    "last_route_type": None,
    "pending_action": None,  # Visible priority pending (compat)
    "pending_slots": {
        "live_ops": None,
        "memory": None,
    },
    "last_live_ops_issue": None,
    "owner_corrections": [],
    "concise_mode": False,
    "last_owner_message_summary": None,
    "timestamp": None
}

_session_trace = {
    "session_backend": "local_fallback",
    "redis_available": False,
    "pending_state_source": None,
    "redis_fallback_reason": None,
}

# Persistent owner-preference keys (survive backend restarts via Redis).
_CORRECTIONS_KEY = "owner_style_corrections"
_CONCISE_MODE_KEY = "owner_concise_mode"
_MAX_CORRECTIONS = 12
_corrections_hydrated = False
_concise_hydrated = False
_session_hydrated = False


def _refresh_redis_available() -> dict:
    info = redis_state.is_redis_available()
    _session_trace["redis_available"] = bool(info.get("available"))
    return info


def get_session_trace_info() -> dict:
    return dict(_session_trace)


def _mirror_session_snapshot_to_redis() -> None:
    info = _refresh_redis_available()
    if not info.get("available"):
        _session_trace["session_backend"] = "local_fallback"
        _session_trace["redis_fallback_reason"] = info.get("reason") or "redis_unavailable"
        return
    snapshot = {
        "last_intent": _state.get("last_intent"),
        "last_route_type": _state.get("last_route_type"),
        "last_live_ops_issue": _state.get("last_live_ops_issue"),
        "last_owner_message_summary": _state.get("last_owner_message_summary"),
        "timestamp": _state.get("timestamp"),
        "owner_corrections_count": len(_state.get("owner_corrections") or []),
    }
    saved = redis_state.save_live_session_snapshot(snapshot)
    if saved.get("success"):
        _session_trace["session_backend"] = "redis"
        _session_trace["redis_fallback_reason"] = None
    else:
        _session_trace["session_backend"] = "local_fallback"
        _session_trace["redis_fallback_reason"] = saved.get("reason") or "redis_save_failed"


def _hydrate_session_from_redis_snapshot() -> None:
    """Restore short-term session context from Redis once per process (restart-safe)."""
    global _session_hydrated
    if _session_hydrated:
        return
    _session_hydrated = True
    res = redis_state.get_live_session_snapshot()
    snapshot = res.get("snapshot") if res.get("success") else None
    if not snapshot:
        return
    for key in ("last_intent", "last_route_type", "last_live_ops_issue", "last_owner_message_summary", "timestamp"):
        if snapshot.get(key) is not None:
            _state[key] = snapshot.get(key)


def record_turn(intent: str | None, route_type: str | None, owner_message: str) -> None:
    """Record per-turn short-term session state and mirror it to Redis (primary).

    Called once per conversation turn so Neena keeps live session continuity
    (last intent/route/message) in Redis, surviving restarts and multi-worker."""
    if intent:
        _state["last_intent"] = intent
    if route_type:
        _state["last_route_type"] = route_type
    if owner_message:
        summary = owner_message.strip()
        _state["last_owner_message_summary"] = summary[:100] + ("..." if len(summary) > 100 else "")
    _state["timestamp"] = datetime.now().isoformat()
    _mirror_session_snapshot_to_redis()
    age_pending_after_turn()


def get_state() -> dict:
    """Returns a copy of the current short-term state."""
    return dict(_state)


def _pending_slot_for(*, category: str | None, action_type: str | None, protected: bool) -> str:
    cat = (category or "").strip().lower()
    at = (action_type or "").strip().lower()
    if cat == "memory" or at in ("memory_edit", "permanent_memory_save"):
        return redis_state.PENDING_SLOT_MEMORY
    if protected or cat in ("live_ops", "broadcast", "protected"):
        return redis_state.PENDING_SLOT_LIVE_OPS
    # Default: treat as live_ops so confirm gates stay frictionless.
    return redis_state.PENDING_SLOT_LIVE_OPS


def _priority_pending_from_slots() -> dict | None:
    slots = _state.get("pending_slots") or {}
    for key in (redis_state.PENDING_SLOT_LIVE_OPS, redis_state.PENDING_SLOT_MEMORY):
        action = slots.get(key)
        if isinstance(action, dict) and action:
            return action
    return None


def set_pending_action(
    action_type: str,
    category: str,
    risk_level: str,
    protected: bool,
    executable_now: bool,
    requires_stage: str,
    allowed_tool: str = None,
    status: str = "blocked_pending_stage",
    expires_after_turns: int = 1,
    payload: dict = None
):
    """
    Explicitly registers a pending action in short-term state.
    Redis primary when available; always mirrors to local state.
    Memory vs live_ops use separate slots so they do not overwrite each other.
    """
    slot = _pending_slot_for(
        category=category, action_type=action_type, protected=bool(protected)
    )
    action_dict = {
        "action_id": str(uuid.uuid4()),
        "action_type": action_type,
        "category": category,
        "risk_level": risk_level,
        "protected": protected,
        "executable_now": executable_now,
        "requires_stage": requires_stage,
        "allowed_tool": allowed_tool,
        "status": status,
        "created_at": datetime.now().isoformat(),
        "expires_after_turns": int(expires_after_turns or 1),
        "turns_remaining": int(expires_after_turns or 1),
        "skip_age_once": True,
        "slot": slot,
        "payload": payload or {}
    }
    slots = dict(_state.get("pending_slots") or {})
    slots[slot] = action_dict
    _state["pending_slots"] = slots
    _state["pending_action"] = _priority_pending_from_slots()
    _state["timestamp"] = datetime.now().isoformat()

    info = _refresh_redis_available()
    if info.get("available"):
        saved = redis_state.save_live_pending_action(action_dict, slot=slot)
        if saved.get("success"):
            _session_trace["session_backend"] = "redis"
            _session_trace["pending_state_source"] = "redis"
            _session_trace["redis_fallback_reason"] = None
        else:
            _session_trace["session_backend"] = "local_fallback"
            _session_trace["pending_state_source"] = "local"
            _session_trace["redis_fallback_reason"] = saved.get("reason") or "redis_save_failed"
    else:
        _session_trace["session_backend"] = "local_fallback"
        _session_trace["pending_state_source"] = "local"
        _session_trace["redis_fallback_reason"] = info.get("reason") or "redis_unavailable"


def get_pending_action() -> dict or None:
    """
    Returns the current pending action dict, or None if not set.
    Priority: live_ops > memory > legacy. Redis-first when available.
    """
    info = _refresh_redis_available()
    if info.get("available"):
        slots = {"live_ops": None, "memory": None}
        for candidate in (redis_state.PENDING_SLOT_LIVE_OPS, redis_state.PENDING_SLOT_MEMORY):
            loaded = redis_state.get_live_pending_action(slot=candidate)
            action = loaded.get("action") if loaded.get("success") else None
            if isinstance(action, dict) and action:
                action = dict(action)
                action.setdefault("slot", candidate)
                slots[candidate] = action
        if not slots["live_ops"] and not slots["memory"]:
            # Legacy single-key fallback (pre-namespace).
            legacy = redis_state.get_live_pending_action(slot="legacy")
            action = legacy.get("action") if legacy.get("success") else None
            if isinstance(action, dict) and action:
                slot = _pending_slot_for(
                    category=action.get("category"),
                    action_type=action.get("action_type"),
                    protected=bool(action.get("protected")),
                )
                action = dict(action)
                action["slot"] = slot
                slots[slot] = action
                # Migrate into namespaced key.
                redis_state.save_live_pending_action(action, slot=slot)
                redis_state.clear_live_pending_action(slot="legacy")

        _state["pending_slots"] = slots
        action = _priority_pending_from_slots()
        _state["pending_action"] = action
        _session_trace["session_backend"] = "redis"
        _session_trace["pending_state_source"] = "redis" if action else None
        _session_trace["redis_fallback_reason"] = None
        return action

    _hydrate_session_from_redis_snapshot()
    _session_trace["session_backend"] = "local_fallback"
    _session_trace["pending_state_source"] = "local"
    _session_trace["redis_fallback_reason"] = info.get("reason") or "redis_unavailable"
    return _priority_pending_from_slots()


def clear_pending_action(slot: str | None = None):
    """
    Clears pending. Default: only the active priority slot (sibling survives).
    Pass slot='all' to wipe every pending namespace.
    """
    if slot is None:
        pending = _priority_pending_from_slots()
        if isinstance(pending, dict) and pending.get("slot"):
            slot = pending.get("slot")
        elif isinstance(pending, dict):
            slot = _pending_slot_for(
                category=pending.get("category"),
                action_type=pending.get("action_type"),
                protected=bool(pending.get("protected")),
            )
        else:
            slot = "all"

    slots = dict(_state.get("pending_slots") or {})
    if slot == "all":
        slots = {"live_ops": None, "memory": None}
        clear_slot = None
    elif slot in (redis_state.PENDING_SLOT_LIVE_OPS, redis_state.PENDING_SLOT_MEMORY):
        slots[slot] = None
        clear_slot = slot
    else:
        slots = {"live_ops": None, "memory": None}
        clear_slot = None

    _state["pending_slots"] = slots
    _state["pending_action"] = _priority_pending_from_slots()
    _state["timestamp"] = datetime.now().isoformat()
    info = _refresh_redis_available()
    if info.get("available"):
        redis_state.clear_live_pending_action(slot=clear_slot)


def age_pending_after_turn() -> None:
    """Decrement turns_remaining on pending slots; clear when expired.

    Newly-set pending has skip_age_once so the setting turn does not consume TTL.
    """
    # Prefer Redis slots when available so aging sees both namespaces.
    info = _refresh_redis_available()
    slots = dict(_state.get("pending_slots") or {})
    if info.get("available"):
        for key in (redis_state.PENDING_SLOT_LIVE_OPS, redis_state.PENDING_SLOT_MEMORY):
            loaded = redis_state.get_live_pending_action(slot=key)
            action = loaded.get("action") if loaded.get("success") else None
            slots[key] = action if isinstance(action, dict) else None

    changed = False
    for key in (redis_state.PENDING_SLOT_LIVE_OPS, redis_state.PENDING_SLOT_MEMORY):
        action = slots.get(key)
        if not isinstance(action, dict) or not action:
            continue
        if action.get("skip_age_once"):
            action = dict(action)
            action["skip_age_once"] = False
            action.setdefault("slot", key)
            slots[key] = action
            changed = True
            if info.get("available"):
                redis_state.save_live_pending_action(action, slot=key)
            continue
        remaining = int(action.get("turns_remaining") or action.get("expires_after_turns") or 1)
        remaining -= 1
        if remaining <= 0:
            slots[key] = None
            changed = True
            if info.get("available"):
                redis_state.clear_live_pending_action(slot=key)
        else:
            action = dict(action)
            action["turns_remaining"] = remaining
            action.setdefault("slot", key)
            slots[key] = action
            changed = True
            if info.get("available"):
                redis_state.save_live_pending_action(action, slot=key)
    if changed:
        _state["pending_slots"] = slots
        _state["pending_action"] = _priority_pending_from_slots()
        _state["timestamp"] = datetime.now().isoformat()
    else:
        _state["pending_slots"] = slots
        _state["pending_action"] = _priority_pending_from_slots()

def get_safe_pending_action_context_json() -> str:
    """
    Returns a compact safe JSON string representing the active pending action.
    Returns empty string if no pending action is active.
    Uses Redis-aware get_pending_action() (ADR-008).
    """
    pending = get_pending_action()
    if not pending:
        return ""
    
    # Only serialize safe fields
    safe_fields = {
        "action_type": pending.get("action_type"),
        "category": pending.get("category"),
        "risk_level": pending.get("risk_level"),
        "protected": pending.get("protected"),
        "executable_now": pending.get("executable_now"),
        "requires_stage": pending.get("requires_stage"),
        "status": pending.get("status"),
        "expires_after_turns": pending.get("expires_after_turns"),
        "turns_remaining": pending.get("turns_remaining"),
        "slot": pending.get("slot"),
    }
    payload = pending.get("payload") or {}
    memory_candidate = payload.get("memory_candidate") or {}
    if pending.get("action_type") == "permanent_memory_save":
        safe_fields["memory_candidate_active"] = True
        safe_fields["memory_type"] = memory_candidate.get("memory_type")
    return json.dumps(safe_fields)

def _hydrate_corrections_from_redis() -> None:
    """Load persisted style corrections once so they survive a backend restart."""
    global _corrections_hydrated
    if _corrections_hydrated:
        return
    info = _refresh_redis_available()
    if info.get("available"):
        res = redis_state.get_session_state(_CORRECTIONS_KEY)
        raw = res.get("value") if res.get("success") else None
        if raw:
            try:
                stored = json.loads(raw)
                if isinstance(stored, list):
                    _state["owner_corrections"] = [str(x) for x in stored][-_MAX_CORRECTIONS:]
            except (ValueError, TypeError):
                pass
    _corrections_hydrated = True


def _persist_corrections_to_redis() -> None:
    info = _refresh_redis_available()
    if info.get("available"):
        redis_state.set_session_state(
            _CORRECTIONS_KEY, json.dumps(_state["owner_corrections"])
        )


def remember_owner_correction(text: str):
    """
    Saves a text correction/style preference. Persisted to Redis so it is not lost
    on backend restart (in-memory list is only a mirror).
    """
    _hydrate_corrections_from_redis()
    clean_text = text.strip()
    if clean_text and clean_text not in _state["owner_corrections"]:
        _state["owner_corrections"].append(clean_text)
        _state["owner_corrections"] = _state["owner_corrections"][-_MAX_CORRECTIONS:]
        _persist_corrections_to_redis()
    _state["timestamp"] = datetime.now().isoformat()
    _mirror_session_snapshot_to_redis()


def _hydrate_concise_from_redis() -> None:
    """Load persisted concise preference once (restart-safe); then read from _state."""
    global _concise_hydrated
    if _concise_hydrated:
        return
    info = _refresh_redis_available()
    if info.get("available"):
        res = redis_state.get_session_state(_CONCISE_MODE_KEY)
        if res.get("success") and res.get("value") is not None:
            _state["concise_mode"] = str(res.get("value")).strip() == "1"
    _concise_hydrated = True


def get_owner_corrections() -> list:
    """Return persisted style/rule corrections (hydrates from Redis first)."""
    _hydrate_corrections_from_redis()
    return list(_state.get("owner_corrections") or [])


def set_response_style(concise: bool) -> None:
    """Persist the owner's verbosity preference (short vs normal replies)."""
    global _concise_hydrated
    _state["concise_mode"] = bool(concise)
    _concise_hydrated = True
    info = _refresh_redis_available()
    if info.get("available"):
        redis_state.set_session_state(_CONCISE_MODE_KEY, "1" if concise else "0")
    if concise:
        remember_owner_correction("Owner prefers short, concise replies — avoid full data dumps unless asked.")


def is_concise_mode() -> bool:
    """True if the owner asked for short replies (Redis-backed, restart-safe).

    Hydrates once from Redis, then reads from the local mirror to avoid a Redis
    round-trip on every status/diagnostics render.
    """
    _hydrate_concise_from_redis()
    return bool(_state.get("concise_mode"))

def build_short_context() -> str:
    """
    Generates a compact safe system context block containing short-term state.
    Excludes secrets, credentials, API keys, raw prompts, or chain-of-thought.
    """
    _hydrate_corrections_from_redis()
    _hydrate_session_from_redis_snapshot()
    lines = ["SHORT-TERM MANAGER STATE:"]
    if _state["last_intent"]:
        lines.append(f"- Last Intent: {_state['last_intent']}")
    if _state["last_route_type"]:
        lines.append(f"- Last Route Type: {_state['last_route_type']}")
    
    pending = get_pending_action()
    if pending:
        lines.append(f"- Pending Action Context: {get_safe_pending_action_context_json()}")
        
    if _state["last_live_ops_issue"]:
        lines.append(f"- Last Live Ops Issue: {_state['last_live_ops_issue']}")
    if _state["owner_corrections"]:
        lines.append("- Active Rules & Style Preferences:")
        for idx, corr in enumerate(_state["owner_corrections"], 1):
            lines.append(f"  {idx}. {corr}")
    if _state["last_owner_message_summary"]:
        lines.append(f"- Last Message Summary: {_state['last_owner_message_summary']}")
        
    return "\n".join(lines)

"""
M2-A6 live Redis session/pending-state adapter with local manager state fallback.

Redis is primary for pending approval/session when available.
Shadow-prefixed helpers remain for M2-A1 smoke tests.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

SHADOW_MODE = False
LIVE_SESSION_BACKEND = "redis_primary"
PENDING_KEY_PREFIX = "neena:shadow:pending:"
SESSION_KEY_PREFIX = "neena:shadow:session:"
LIVE_PENDING_ACTION_KEY = "neena:live:pending_action"  # legacy single-slot (read fallback)
LIVE_PENDING_LIVE_OPS_KEY = "neena:live:pending_action:live_ops"
LIVE_PENDING_MEMORY_KEY = "neena:live:pending_action:memory"
LIVE_SESSION_SNAPSHOT_KEY = "neena:live:session_snapshot"
SELF_FINGERPRINT_KEY = "neena:self:capability_fingerprint"
SELF_CHANGE_PENDING_KEY = "neena:self:pending_change_announce"
# Fingerprint should outlive typical WC — no silent drop between weekly deploys.
SELF_FINGERPRINT_TTL_SECONDS = 60 * 60 * 24 * 90
SELF_CHANGE_PENDING_TTL_SECONDS = 60 * 60 * 24 * 14
OWNER_WORKING_CONTEXT_KEY = "neena:live:owner_working_context"
OWNER_WORKING_CONTEXT_TTL_SECONDS = 7 * 24 * 3600
# Align session snapshot with WC — was 1h and caused idle continuity gaps.
SESSION_SNAPSHOT_TTL_SECONDS = OWNER_WORKING_CONTEXT_TTL_SECONDS
FEATURE_FLAG_OVERRIDES_KEY = "neena:live:feature_flag_overrides"
FEATURE_FLAG_OVERRIDES_TTL_SECONDS = 30 * 24 * 3600
LIVE_PENDING_TTL_SECONDS = 7 * 24 * 3600

PENDING_SLOT_LIVE_OPS = "live_ops"
PENDING_SLOT_MEMORY = "memory"
_PENDING_SLOT_KEYS = {
    PENDING_SLOT_LIVE_OPS: LIVE_PENDING_LIVE_OPS_KEY,
    PENDING_SLOT_MEMORY: LIVE_PENDING_MEMORY_KEY,
}

_REDIS_IMPORT_ERROR: str | None = None
try:
    import redis
except ImportError as exc:
    redis = None  # type: ignore[assignment]
    _REDIS_IMPORT_ERROR = str(exc)


def _redis_config() -> dict[str, Any]:
    return {
        "host": os.environ.get("NEENA_REDIS_HOST", "127.0.0.1"),
        "port": int(os.environ.get("NEENA_REDIS_PORT", "6379")),
        "db": int(os.environ.get("NEENA_REDIS_DB", "0")),
        "password": os.environ.get("NEENA_REDIS_PASSWORD") or None,
        "socket_connect_timeout": 3,
        "decode_responses": True,
    }


def _unavailable(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "shadow_mode": SHADOW_MODE,
        "live_session_backend": LIVE_SESSION_BACKEND,
        "reason": reason,
    }
    payload.update(extra)
    return payload


_REDIS_CLIENT_INSTANCE = None


def _client():
    global _REDIS_CLIENT_INSTANCE
    if _REDIS_CLIENT_INSTANCE is None:
        if redis is None:
            raise RuntimeError(_REDIS_IMPORT_ERROR or "redis_not_installed")
        cfg = _redis_config()
        _REDIS_CLIENT_INSTANCE = redis.Redis(
            host=cfg["host"],
            port=cfg["port"],
            db=cfg["db"],
            password=cfg["password"],
            socket_connect_timeout=cfg["socket_connect_timeout"],
            decode_responses=True,
        )
    return _REDIS_CLIENT_INSTANCE


def is_redis_available() -> dict[str, Any]:
    if redis is None:
        return _unavailable("redis_not_installed")
    try:
        client = _client()
        client.ping()
        return {
            "available": True,
            "shadow_mode": SHADOW_MODE,
            "live_session_backend": LIVE_SESSION_BACKEND,
            "host": _redis_config()["host"],
            "port": _redis_config()["port"],
            "db": _redis_config()["db"],
        }
    except Exception as exc:
        return _unavailable("redis_connection_failed", error_type=type(exc).__name__)


def set_session_state(key: str, value: str, ttl_seconds: int | None = None) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not key:
        return {**_unavailable("session_key_empty"), "success": False}
    try:
        client = _client()
        redis_key = f"{SESSION_KEY_PREFIX}{key}"
        if ttl_seconds is not None and ttl_seconds > 0:
            client.setex(redis_key, int(ttl_seconds), value)
        else:
            client.set(redis_key, value)
        return {"success": True, "key": key, "shadow_mode": SHADOW_MODE}
    except Exception as exc:
        return {**_unavailable("set_session_failed", error_type=type(exc).__name__), "success": False}


def get_session_state(key: str) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "value": None}
    if not key:
        return {**_unavailable("session_key_empty"), "value": None}
    try:
        client = _client()
        value = client.get(f"{SESSION_KEY_PREFIX}{key}")
        return {"success": True, "key": key, "value": value}
    except Exception as exc:
        return {**_unavailable("get_session_failed", error_type=type(exc).__name__), "value": None}


def delete_session_state(key: str) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not key:
        return {**_unavailable("session_key_empty"), "success": False}
    try:
        client = _client()
        deleted = client.delete(f"{SESSION_KEY_PREFIX}{key}")
        return {"success": deleted > 0, "key": key, "deleted": deleted > 0}
    except Exception as exc:
        return {**_unavailable("delete_session_failed", error_type=type(exc).__name__), "success": False}


def save_pending_memory_candidate(candidate_key: str, candidate: dict) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not candidate_key:
        return {**_unavailable("candidate_key_empty"), "success": False}
    try:
        client = _client()
        redis_key = f"{PENDING_KEY_PREFIX}{candidate_key}"
        client.set(redis_key, json.dumps(candidate, ensure_ascii=False))
        return {"success": True, "candidate_key": candidate_key, "shadow_mode": SHADOW_MODE}
    except Exception as exc:
        return {**_unavailable("save_pending_failed", error_type=type(exc).__name__), "success": False}


def get_pending_memory_candidate(candidate_key: str) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "candidate": None}
    if not candidate_key:
        return {**_unavailable("candidate_key_empty"), "candidate": None}
    try:
        client = _client()
        raw = client.get(f"{PENDING_KEY_PREFIX}{candidate_key}")
        if not raw:
            return {"success": True, "candidate_key": candidate_key, "candidate": None}
        candidate = json.loads(raw)
        return {"success": True, "candidate_key": candidate_key, "candidate": candidate}
    except Exception as exc:
        return {**_unavailable("get_pending_failed", error_type=type(exc).__name__), "candidate": None}


def clear_pending_memory_candidate(candidate_key: str) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not candidate_key:
        return {**_unavailable("candidate_key_empty"), "success": False}
    try:
        client = _client()
        deleted = client.delete(f"{PENDING_KEY_PREFIX}{candidate_key}")
        return {"success": deleted > 0, "candidate_key": candidate_key, "deleted": deleted > 0}
    except Exception as exc:
        return {**_unavailable("clear_pending_failed", error_type=type(exc).__name__), "success": False}


def _pending_redis_key(slot: str | None) -> str:
    if slot in _PENDING_SLOT_KEYS:
        return _PENDING_SLOT_KEYS[slot]
    if slot == "legacy":
        return LIVE_PENDING_ACTION_KEY
    return LIVE_PENDING_ACTION_KEY


def save_live_pending_action(
    action: dict,
    ttl_seconds: int | None = LIVE_PENDING_TTL_SECONDS,
    *,
    slot: str | None = None,
) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not action:
        return {**_unavailable("pending_action_empty"), "success": False}
    try:
        client = _client()
        payload = json.dumps(action, ensure_ascii=False)
        key = _pending_redis_key(slot)
        if ttl_seconds is not None and ttl_seconds > 0:
            client.setex(key, int(ttl_seconds), payload)
        else:
            client.set(key, payload)
        if slot in _PENDING_SLOT_KEYS:
            client.delete(LIVE_PENDING_ACTION_KEY)
        return {"success": True, "live_mode": True, "slot": slot or "legacy"}
    except Exception as exc:
        return {**_unavailable("save_live_pending_failed", error_type=type(exc).__name__), "success": False}


def get_live_pending_action(*, slot: str | None = None) -> dict[str, Any]:
    """Load pending. With slot=None: live_ops > memory > legacy (priority)."""
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "action": None}
    try:
        client = _client()
        if slot is not None:
            raw = client.get(_pending_redis_key(slot))
            if not raw:
                return {"success": True, "action": None, "slot": slot}
            return {"success": True, "action": json.loads(raw), "slot": slot}

        for candidate in (PENDING_SLOT_LIVE_OPS, PENDING_SLOT_MEMORY):
            raw = client.get(_PENDING_SLOT_KEYS[candidate])
            if raw:
                return {
                    "success": True,
                    "action": json.loads(raw),
                    "slot": candidate,
                }
        raw = client.get(LIVE_PENDING_ACTION_KEY)
        if not raw:
            return {"success": True, "action": None, "slot": None}
        return {"success": True, "action": json.loads(raw), "slot": "legacy"}
    except Exception as exc:
        return {**_unavailable("get_live_pending_failed", error_type=type(exc).__name__), "action": None}


def clear_live_pending_action(*, slot: str | None = None) -> dict[str, Any]:
    """Clear one slot, or all pending keys when slot is None / 'all'."""
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        client = _client()
        if slot in _PENDING_SLOT_KEYS:
            deleted = client.delete(_PENDING_SLOT_KEYS[slot])
            return {"success": True, "deleted": deleted > 0, "slot": slot}
        if slot == "legacy":
            deleted = client.delete(LIVE_PENDING_ACTION_KEY)
            return {"success": True, "deleted": deleted > 0, "slot": "legacy"}
        deleted = 0
        for key in list(_PENDING_SLOT_KEYS.values()) + [LIVE_PENDING_ACTION_KEY]:
            deleted += int(client.delete(key) or 0)
        return {"success": True, "deleted": deleted > 0, "slot": "all"}
    except Exception as exc:
        return {**_unavailable("clear_live_pending_failed", error_type=type(exc).__name__), "success": False}

def save_live_session_snapshot(
    snapshot: dict,
    ttl_seconds: int = SESSION_SNAPSHOT_TTL_SECONDS,
) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        client = _client()
        client.setex(
            LIVE_SESSION_SNAPSHOT_KEY,
            int(ttl_seconds),
            json.dumps(snapshot, ensure_ascii=False),
        )
        return {"success": True}
    except Exception as exc:
        return {**_unavailable("save_session_snapshot_failed", error_type=type(exc).__name__), "success": False}


def get_live_session_snapshot() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "snapshot": None}
    try:
        client = _client()
        raw = client.get(LIVE_SESSION_SNAPSHOT_KEY)
        if not raw:
            return {"success": True, "snapshot": None}
        return {"success": True, "snapshot": json.loads(raw)}
    except Exception as exc:
        return {**_unavailable("get_session_snapshot_failed", error_type=type(exc).__name__), "snapshot": None}


def save_owner_working_context(ctx: dict, ttl_seconds: int = OWNER_WORKING_CONTEXT_TTL_SECONDS) -> dict[str, Any]:
    """Owner-only Cursor-like scratchpad (no secrets). Redis primary."""
    if not isinstance(ctx, dict) or not ctx:
        return {**_unavailable("working_context_empty"), "success": False}
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        client = _client()
        client.setex(
            OWNER_WORKING_CONTEXT_KEY,
            int(ttl_seconds),
            json.dumps(ctx, ensure_ascii=False, default=str),
        )
        return {"success": True}
    except Exception as exc:
        return {
            **_unavailable("save_working_context_failed", error_type=type(exc).__name__),
            "success": False,
        }


def get_owner_working_context() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "context": None}
    try:
        client = _client()
        raw = client.get(OWNER_WORKING_CONTEXT_KEY)
        if not raw:
            return {"success": True, "context": None}
        data = json.loads(raw)
        return {"success": True, "context": data if isinstance(data, dict) else None}
    except Exception as exc:
        return {
            **_unavailable("get_working_context_failed", error_type=type(exc).__name__),
            "context": None,
        }


def save_feature_flag_overrides(
    overrides: dict, ttl_seconds: int = FEATURE_FLAG_OVERRIDES_TTL_SECONDS
) -> dict[str, Any]:
    """Persist CC feature-flag overrides (bool map). Empty dict clears key."""
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        client = _client()
        if not overrides:
            client.delete(FEATURE_FLAG_OVERRIDES_KEY)
            return {"success": True}
        client.setex(
            FEATURE_FLAG_OVERRIDES_KEY,
            int(ttl_seconds),
            json.dumps(overrides, ensure_ascii=False),
        )
        return {"success": True}
    except Exception as exc:
        return {
            **_unavailable("save_flag_overrides_failed", error_type=type(exc).__name__),
            "success": False,
        }


def get_feature_flag_overrides() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "overrides": None}
    try:
        client = _client()
        raw = client.get(FEATURE_FLAG_OVERRIDES_KEY)
        if not raw:
            return {"success": True, "overrides": {}}
        data = json.loads(raw)
        return {"success": True, "overrides": data if isinstance(data, dict) else {}}
    except Exception as exc:
        return {
            **_unavailable("get_flag_overrides_failed", error_type=type(exc).__name__),
            "overrides": None,
        }


# Customer WhatsApp short-term chat (per phone). Owner path never uses these keys.
CUSTOMER_CHAT_KEY_PREFIX = "customer_chat:"
CUSTOMER_CHAT_TTL_SECONDS = 7 * 24 * 3600
CUSTOMER_CHAT_MAX_TURNS = 12


def _customer_chat_key(phone_digits: str) -> str:
    digits = "".join(c for c in (phone_digits or "") if c.isdigit())
    tail = digits[-10:] if len(digits) >= 10 else (digits or "unknown")
    return f"{CUSTOMER_CHAT_KEY_PREFIX}{tail}"


def get_customer_chat_turns(phone_digits: str, limit: int = 8) -> list[dict[str, str]]:
    """Recent customer WhatsApp turns for one phone. Empty if Redis down / no history."""
    key = _customer_chat_key(phone_digits)
    got = get_session_state(key)
    raw = got.get("value") if got.get("success") else None
    if not raw:
        return []
    try:
        turns = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(turns, list):
        return []
    out: list[dict[str, str]] = []
    for item in turns[-max(1, int(limit)) :]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        text = str(item.get("text") or "").strip()
        if role in ("user", "assistant") and text:
            out.append({"role": role, "text": text[:800]})
    return out


def append_customer_chat_turn(phone_digits: str, role: str, text: str) -> dict[str, Any]:
    """Append one customer chat turn (user|assistant). No-op if phone/text empty."""
    role_n = (role or "").strip().lower()
    text_n = (text or "").strip()
    if role_n not in ("user", "assistant") or not text_n:
        return {"success": False, "reason": "invalid_turn"}
    key = _customer_chat_key(phone_digits)
    turns = get_customer_chat_turns(phone_digits, limit=CUSTOMER_CHAT_MAX_TURNS)
    turns.append({"role": role_n, "text": text_n[:800]})
    turns = turns[-CUSTOMER_CHAT_MAX_TURNS:]
    return set_session_state(
        key,
        json.dumps(turns, ensure_ascii=False),
        ttl_seconds=CUSTOMER_CHAT_TTL_SECONDS,
    )


def save_self_fingerprint(fingerprint: dict, ttl_seconds: int = SELF_FINGERPRINT_TTL_SECONDS) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not isinstance(fingerprint, dict):
        return {**_unavailable("fingerprint_invalid"), "success": False}
    try:
        client = _client()
        payload = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True)
        client.setex(SELF_FINGERPRINT_KEY, int(ttl_seconds), payload)
        return {"success": True}
    except Exception as exc:
        return {**_unavailable("save_self_fingerprint_failed", error_type=type(exc).__name__), "success": False}


def get_self_fingerprint() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "fingerprint": None}
    try:
        raw = _client().get(SELF_FINGERPRINT_KEY)
        if not raw:
            return {"success": True, "fingerprint": None}
        data = json.loads(raw)
        return {"success": True, "fingerprint": data if isinstance(data, dict) else None}
    except Exception as exc:
        return {
            **_unavailable("get_self_fingerprint_failed", error_type=type(exc).__name__),
            "fingerprint": None,
        }


def save_self_change_pending(
    pending: dict,
    ttl_seconds: int = SELF_CHANGE_PENDING_TTL_SECONDS,
) -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not isinstance(pending, dict):
        return {**_unavailable("pending_invalid"), "success": False}
    try:
        client = _client()
        client.setex(
            SELF_CHANGE_PENDING_KEY,
            int(ttl_seconds),
            json.dumps(pending, ensure_ascii=False),
        )
        return {"success": True}
    except Exception as exc:
        return {**_unavailable("save_self_change_pending_failed", error_type=type(exc).__name__), "success": False}


def get_self_change_pending() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "pending": None}
    try:
        raw = _client().get(SELF_CHANGE_PENDING_KEY)
        if not raw:
            return {"success": True, "pending": None}
        data = json.loads(raw)
        return {"success": True, "pending": data if isinstance(data, dict) else None}
    except Exception as exc:
        return {
            **_unavailable("get_self_change_pending_failed", error_type=type(exc).__name__),
            "pending": None,
        }


def clear_self_change_pending() -> dict[str, Any]:
    base = is_redis_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        deleted = _client().delete(SELF_CHANGE_PENDING_KEY)
        return {"success": True, "deleted": deleted > 0}
    except Exception as exc:
        return {**_unavailable("clear_self_change_pending_failed", error_type=type(exc).__name__), "success": False}


__all__ = [
    "SHADOW_MODE",
    "LIVE_SESSION_BACKEND",
    "is_redis_available",
    "set_session_state",
    "get_session_state",
    "delete_session_state",
    "save_pending_memory_candidate",
    "get_pending_memory_candidate",
    "clear_pending_memory_candidate",
    "save_live_pending_action",
    "get_live_pending_action",
    "clear_live_pending_action",
    "save_live_session_snapshot",
    "get_live_session_snapshot",
    "save_owner_working_context",
    "get_owner_working_context",
    "save_feature_flag_overrides",
    "get_feature_flag_overrides",
    "get_customer_chat_turns",
    "append_customer_chat_turn",
    "save_self_fingerprint",
    "get_self_fingerprint",
    "save_self_change_pending",
    "get_self_change_pending",
    "clear_self_change_pending",
]

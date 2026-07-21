"""Daily request Gatekeeper — Observer / chowkidar for free-tier RPM/RPD.

Process-local counters (fast, no Redis hang on hot path). Optional best-effort
Redis mirror for multi-worker later; never blocks generateContent on Redis.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

Priority = Literal["owner_critical", "owner", "customer", "background"]

_LOCK = threading.Lock()
_LOCAL_COUNTS: dict[str, int] = {}
_LOW_COST = False

_DEFAULTS = {
    "gemma": {"warn": 1200, "hard": 1450},
    "lite": {"warn": 400, "hard": 450},
    "embed": {"warn": 900, "hard": 980},
    "other": {"warn": 200, "hard": 250},
}


def _bucket(model_id: str) -> str:
    mid = (model_id or "").lower()
    if "embed" in mid:
        return "embed"
    if "flash-lite" in mid or "flash_lite" in mid or "1.5-flash" in mid:
        return "lite"
    if "gemma" in mid:
        return "gemma"
    return "other"


def _caps(bucket: str) -> tuple[int, int]:
    base = _DEFAULTS.get(bucket, _DEFAULTS["other"])
    warn = int(os.environ.get(f"NEENA_QUOTA_WARN_{bucket.upper()}", base["warn"]))
    hard = int(os.environ.get(f"NEENA_QUOTA_HARD_{bucket.upper()}", base["hard"]))
    return max(1, warn), max(warn, hard)


def _day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _counter_key(model_id: str) -> str:
    return f"quota:rpd:{_bucket(model_id)}:{_day_key()}"


def _read_count(key: str) -> int:
    with _LOCK:
        return int(_LOCAL_COUNTS.get(key, 0))


def _write_count(key: str, value: int) -> None:
    with _LOCK:
        _LOCAL_COUNTS[key] = int(value)


def get_model_daily_count(model_id: str) -> int:
    return _read_count(_counter_key(model_id))


def record_success(model_id: str) -> int:
    key = _counter_key(model_id)
    with _LOCK:
        n = int(_LOCAL_COUNTS.get(key, 0)) + 1
        _LOCAL_COUNTS[key] = n
    _refresh_low_cost_flag()
    return n


def _refresh_low_cost_flag() -> bool:
    global _LOW_COST
    day = _day_key()
    g_warn, _ = _caps("gemma")
    l_warn, _ = _caps("lite")
    g_n = _read_count(f"quota:rpd:gemma:{day}")
    l_n = _read_count(f"quota:rpd:lite:{day}")
    _LOW_COST = g_n >= g_warn or l_n >= l_warn
    return _LOW_COST


def low_cost_mode_enabled() -> bool:
    return _refresh_low_cost_flag()


def agent_loop_max_steps(default_bounded: int = 5, default_deep: int = 8, *, deep: bool = False) -> int:
    if low_cost_mode_enabled():
        return 1
    return default_deep if deep else default_bounded


def evaluate_request(
    model_id: str,
    *,
    priority: Priority = "owner",
    purpose: str = "chat",
) -> dict[str, Any]:
    """Decide allow / force_lite / defer before an HTTP call.

    Never blocks owner_critical at hard cap. Embed hard-cap → quota_skip_embed.
    """
    bucket = _bucket(model_id)
    warn, hard = _caps(bucket)
    count = get_model_daily_count(model_id)
    low = low_cost_mode_enabled() or count >= warn

    if bucket == "embed" and count >= hard:
        return {
            "allow": False,
            "status": "quota_skip_embed",
            "low_cost": True,
            "force_lite": False,
            "count": count,
            "hard": hard,
            "reason": "embed_daily_hard",
        }

    if count >= hard and priority != "owner_critical":
        return {
            "allow": False,
            "status": "quota_deferred",
            "low_cost": True,
            "force_lite": bucket == "gemma",
            "count": count,
            "hard": hard,
            "reason": f"{bucket}_daily_hard",
        }

    force_lite = low and bucket == "gemma" and purpose in (
        "conversation",
        "customer",
        "agent_step",
        "interpreter",
        "chat",
    )
    return {
        "allow": True,
        "status": "ok",
        "low_cost": low,
        "force_lite": bool(force_lite),
        "count": count,
        "warn": warn,
        "hard": hard,
        "reason": "ok",
    }


def quota_snapshot() -> dict[str, Any]:
    day = _day_key()
    out: dict[str, Any] = {"day_utc": day, "low_cost_mode": low_cost_mode_enabled(), "buckets": {}}
    for b in ("gemma", "lite", "embed", "other"):
        warn, hard = _caps(b)
        n = _read_count(f"quota:rpd:{b}:{day}")
        out["buckets"][b] = {"count": n, "warn": warn, "hard": hard}
    return out


def build_quota_defer_reply(*, role: str = "owner") -> str:
    if (role or "").lower() == "customer":
        return (
            "Ji, abhi system thoda busy hai (daily AI limit near). "
            "Thodi der baad dubara message kariye."
        )
    return (
        "Sir, aaj ki free AI request limit near hai, isliye naya heavy reply "
        "abhi defer kar rahi hoon. Confirm/haan pending actions safe hain — "
        "thodi der baad status/creative try kariye."
    )


__all__ = [
    "Priority",
    "agent_loop_max_steps",
    "build_quota_defer_reply",
    "evaluate_request",
    "get_model_daily_count",
    "low_cost_mode_enabled",
    "quota_snapshot",
    "record_success",
]

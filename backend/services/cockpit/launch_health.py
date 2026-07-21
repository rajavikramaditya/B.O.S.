"""
M4-A7 — Fast vs deep launch health (non-blocking, cached, no secrets).
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

import services.cockpit.runtime_controller as rc
from services.memory.pg_repository import (
    LIVE_MEMORY_BACKEND,
    is_pgvector_available,
    is_postgres_available,
)
from services.brain.redis_state import LIVE_SESSION_BACKEND, is_redis_available

_DEEP_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_DEEP_CACHE_TTL_SECONDS = 12.0
_CHECK_TIMEOUT_SECONDS = 2.0

_HEALTH_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="diagnostics-pool")


def _memory_stack_offline(health: dict[str, Any]) -> bool:
    return not (
        health.get("postgres_available")
        and health.get("pgvector_available")
        and health.get("redis_available")
    )


def _run_with_timeout(fn, timeout: float):
    future = _HEALTH_POOL.submit(fn)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeout:
        return None


def _collect_memory_health_parallel() -> dict[str, Any]:
    postgres = _run_with_timeout(is_postgres_available, _CHECK_TIMEOUT_SECONDS)
    if postgres is None:
        postgres = {
            "available": False,
            "reason": "postgres_check_timeout",
            "shadow_mode": True,
            "live_memory_backend": LIVE_MEMORY_BACKEND,
        }

    pgvector = None
    if postgres.get("available"):
        pgvector = _run_with_timeout(is_pgvector_available, _CHECK_TIMEOUT_SECONDS)
    if pgvector is None:
        pgvector = {
            "available": False,
            "reason": "pgvector_check_timeout"
            if postgres.get("available")
            else "postgres_unavailable",
        }

    redis = _run_with_timeout(is_redis_available, _CHECK_TIMEOUT_SECONDS)
    if redis is None:
        redis = {
            "available": False,
            "reason": "redis_check_timeout",
            "shadow_mode": False,
            "live_session_backend": LIVE_SESSION_BACKEND,
        }

    postgres_available = bool(postgres.get("available"))
    pgvector_available = bool(pgvector.get("available"))
    redis_available = bool(redis.get("available"))

    return {
        "shadow_mode_only": True,
        "live_memory_backend": LIVE_MEMORY_BACKEND,
        "live_session_backend": LIVE_SESSION_BACKEND,
        "postgres_available": postgres_available,
        "pgvector_available": pgvector_available,
        "redis_available": redis_available,
        "production_memory_shadow_ready": (
            postgres_available and pgvector_available and redis_available
        ),
        "postgres": postgres,
        "pgvector": pgvector,
        "redis": redis,
    }


def get_deep_launch_health(*, force_refresh: bool = False) -> dict[str, Any]:
    """Deep diagnostic health — cached, bounded timeouts, non-blocking WhatsApp."""
    now = time.time()
    cached_at = float(_DEEP_CACHE.get("at") or 0.0)
    if (
        not force_refresh
        and _DEEP_CACHE.get("payload")
        and (now - cached_at) < _DEEP_CACHE_TTL_SECONDS
    ):
        payload = dict(_DEEP_CACHE["payload"])
        payload["cached"] = True
        payload["cache_age_seconds"] = round(now - cached_at, 1)
        return payload

    health = _collect_memory_health_parallel()
    wa = rc.get_whatsapp_gateway_trace_status()
    memory_offline = _memory_stack_offline(health)

    env = os.environ.get("ENVIRONMENT", "").strip().lower()
    insecure_ssl_dev = os.environ.get("ALLOW_INSECURE_SSL_DEV_ONLY", "false").lower() in ("true", "1", "yes")
    insecure_ssl_block = (env == "production" and insecure_ssl_dev)

    shadow_ready = health.get("production_memory_shadow_ready")
    if insecure_ssl_block:
        shadow_ready = False

    payload = {
        "health_tier": "deep_health",
        "backend": "online",
        "postgres": "healthy" if health.get("postgres_available") else "unavailable",
        "pgvector": "active" if health.get("pgvector_available") else "unavailable",
        "redis": "healthy" if health.get("redis_available") else "unavailable",
        "whatsapp_gateway": wa,
        "memory_read": health.get("live_memory_backend") or "unknown",
        "session_backend": health.get("live_session_backend") or "unknown",
        "memory_stack": {
            "postgres": health.get("postgres"),
            "pgvector": health.get("pgvector"),
            "redis": health.get("redis"),
            "production_memory_shadow_ready": shadow_ready,
        },
        "degraded_due_to_memory_stack_offline": memory_offline or insecure_ssl_block,
        "cached": False,
        "check_timeout_seconds": _CHECK_TIMEOUT_SECONDS,
        "insecure_ssl_block": insecure_ssl_block,
        "note": (
            "BLOCKED: Insecure SSL bypass flag cannot be enabled in production environment."
            if insecure_ssl_block
            else (
                "Memory stack offline — shadow PG/Redis tests skip until Docker stack is up."
                if memory_offline
                else "Memory stack reachable."
            )
        ),
    }
    _DEEP_CACHE["at"] = now
    _DEEP_CACHE["payload"] = payload
    return payload


def get_memory_stack_summary_fast() -> dict[str, Any]:
    """Non-blocking snapshot from deep-health cache (no new probes)."""
    cached = _DEEP_CACHE.get("payload")
    if cached:
        return {
            "postgres": cached.get("postgres"),
            "redis": cached.get("redis"),
            "pgvector": cached.get("pgvector"),
            "degraded_due_to_memory_stack_offline": cached.get(
                "degraded_due_to_memory_stack_offline", True
            ),
            "from_cache": True,
        }
    return {
        "postgres": "unknown",
        "redis": "unknown",
        "pgvector": "unknown",
        "degraded_due_to_memory_stack_offline": None,
        "from_cache": False,
        "note": "Deep memory probe not cached yet — open Manual drawer or call /api/neena/launch-health.",
    }


__all__ = ["get_deep_launch_health", "get_memory_stack_summary_fast"]

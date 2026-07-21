"""
Production memory stack health (Postgres/pgvector primary + Redis session).

Reports live availability of the memory backends used by the chat flow.
"""
from __future__ import annotations

from typing import Any

from services.memory.pg_repository import (
    LIVE_MEMORY_BACKEND,
    is_pgvector_available,
    is_postgres_available,
)
from services.brain.redis_state import LIVE_SESSION_BACKEND, is_redis_available


def get_production_memory_shadow_health() -> dict[str, Any]:
    postgres = is_postgres_available()
    pgvector = is_pgvector_available()
    redis = is_redis_available()

    postgres_available = bool(postgres.get("available"))
    pgvector_available = bool(pgvector.get("available"))
    redis_available = bool(redis.get("available"))

    return {
        "shadow_mode_only": False,
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


__all__ = ["get_production_memory_shadow_health"]

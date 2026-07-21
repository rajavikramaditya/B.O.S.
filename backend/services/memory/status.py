"""M4-A8.5 — Owner-safe memory stack status (no secrets). Facts only."""
from __future__ import annotations

import os
from typing import Any

from services.cockpit.launch_health import get_memory_stack_summary_fast

try:
    from services.memory.embedding_provider import PRIMARY_EMBEDDING_MODEL
except Exception:  # pragma: no cover - defensive import
    PRIMARY_EMBEDDING_MODEL = "gemini-embedding-2"


def build_neena_memory_status() -> dict[str, Any]:
    mem = get_memory_stack_summary_fast()
    pg = (mem.get("postgres") or "unknown").lower()
    shadow = os.environ.get("NEENA_MEMORY_SHADOW_MODE", "").strip().lower() in ("1", "true", "yes", "on")
    permanent_enabled = pg in ("healthy", "online", "active") or not mem.get("degraded_due_to_memory_stack_offline")

    return {
        "ok": True,
        "tool": "memory_status",
        "postgres_status": mem.get("postgres", "unknown"),
        "pgvector_status": mem.get("pgvector", "unknown"),
        "redis_session_status": mem.get("redis", "unknown"),
        "permanent_memory_enabled": permanent_enabled,
        "shadow_mode": shadow,
        "live_mode": not shadow,
        "memory_stack_degraded": bool(mem.get("degraded_due_to_memory_stack_offline")),
        "embedding_model": PRIMARY_EMBEDDING_MODEL,
        "recent_writes": None,
        "recent_reads": None,
        "last_memory_error": None,
        "summary": mem,
    }


def build_memory_status_reply() -> str:
    st = build_neena_memory_status()
    mode = "shadow_sqlite_mirror" if st.get("shadow_mode") else "live_postgres_primary"
    parts = [
        "Memory stack status.",
        f"postgres={st.get('postgres_status')}",
        f"pgvector={st.get('pgvector_status')}",
        f"redis_session={st.get('redis_session_status')}",
        f"permanent_memory={'enabled' if st.get('permanent_memory_enabled') else 'degraded'}",
        f"mode={mode}",
        f"degraded={'yes' if st.get('memory_stack_degraded') else 'no'}",
        f"embedding_model={st.get('embedding_model')}",
    ]
    return " ".join(parts)


def build_memory_status_packet() -> dict[str, Any]:
    st = build_neena_memory_status()
    return {
        "factual_packet": st,
        "fallback_line": build_memory_status_reply(),
        "action_type": "MEMORY_STATUS",
    }


__all__ = ["build_memory_status_reply", "build_neena_memory_status", "build_memory_status_packet"]

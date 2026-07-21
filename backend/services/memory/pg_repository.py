"""
PostgreSQL + pgvector memory repository (live primary backend).

PostgreSQL is the primary permanent-memory store with pgvector semantic search.
SQLite is kept only as a mirror / fallback safety net (used when Postgres is
unavailable and for the low-latency creative retrieval fast path).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SHADOW_MODE = False
LIVE_MEMORY_BACKEND = "postgres"
EMBEDDING_VECTOR_DIM = 3072

_PG_IMPORT_ERROR: str | None = None
try:
    import psycopg2
    import psycopg2.extras
except ImportError as exc:
    psycopg2 = None  # type: ignore[assignment]
    _PG_IMPORT_ERROR = str(exc)

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "migrations" / "postgres_memory_schema.sql"
)


def _pg_config() -> dict[str, Any]:
    return {
        "host": os.environ.get("NEENA_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("NEENA_PG_PORT", "5432")),
        "dbname": os.environ.get("NEENA_PG_DB", "neena_memory_shadow"),
        "user": os.environ.get("NEENA_PG_USER", "neena_shadow"),
        "password": os.environ.get("NEENA_PG_PASSWORD", "neena_shadow_dev"),
        "connect_timeout": 3,
    }


def _unavailable(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "shadow_mode": SHADOW_MODE,
        "live_memory_backend": LIVE_MEMORY_BACKEND,
        "reason": reason,
    }
    payload.update(extra)
    return payload


def _connect():
    if psycopg2 is None:
        raise RuntimeError(_PG_IMPORT_ERROR or "psycopg2_not_installed")
    return psycopg2.connect(**_pg_config())


def _decode_row(row: dict | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    raw_metadata = item.get("metadata_json")
    if isinstance(raw_metadata, dict):
        item["metadata"] = raw_metadata
    else:
        try:
            item["metadata"] = json.loads(raw_metadata) if raw_metadata else {}
        except Exception:
            item["metadata"] = {}
    if "embedding_vector" in item and item["embedding_vector"] is not None:
        item["embedding_vector_present"] = True
        item["embedding_vector"] = None
    return item


def _metadata_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in vector) + "]"


def is_postgres_available() -> dict[str, Any]:
    if psycopg2 is None:
        return _unavailable("psycopg2_not_installed")
    try:
        conn = _connect()
        conn.close()
        return {
            "available": True,
            "shadow_mode": SHADOW_MODE,
            "live_memory_backend": LIVE_MEMORY_BACKEND,
            "host": _pg_config()["host"],
            "port": _pg_config()["port"],
            "dbname": _pg_config()["dbname"],
        }
    except Exception as exc:
        return _unavailable("postgres_connection_failed", error_type=type(exc).__name__)


def is_pgvector_available() -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return _unavailable(base.get("reason", "postgres_unavailable"))
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return {
                "available": True,
                "shadow_mode": SHADOW_MODE,
                "extension": "vector",
            }
        return _unavailable("pgvector_extension_missing")
    except Exception as exc:
        return _unavailable("pgvector_check_failed", error_type=type(exc).__name__)


def ensure_postgres_memory_schema() -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    if not _SCHEMA_PATH.exists():
        return {**_unavailable("schema_file_missing"), "success": False}
    try:
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        conn = _connect()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(sql)
        actor_path = _SCHEMA_PATH.parent / "postgres_memory_actor_scope.sql"
        if actor_path.exists():
            cursor.execute(actor_path.read_text(encoding="utf-8"))
        cursor.close()
        conn.close()
        return {
            "success": True,
            "shadow_mode": SHADOW_MODE,
            "tables": ["neena_memories", "neena_memory_events", "neena_activity_logs"],
            "actor_scope": True,
        }
    except Exception as exc:
        logger.warning("PostgreSQL schema ensure failed: %s", type(exc).__name__)
        return {
            "success": False,
            "shadow_mode": SHADOW_MODE,
            "reason": "schema_apply_failed",
            "error_type": type(exc).__name__,
        }


def create_memory_pg(
    memory_type: str,
    content: str,
    owner_confirmed: bool,
    importance: int = 1,
    source: str = "owner_message",
    retention: str = "permanent",
    sensitivity_level: str = "normal",
    expires_at: str | None = None,
    metadata: dict | None = None,
    embedding_model: str | None = None,
    embedding_vector: list[float] | None = None,
    actor_role: str = "owner",
    subject_key: str = "owner",
    salience: float | None = None,
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    if embedding_vector is not None and len(embedding_vector) != EMBEDDING_VECTOR_DIM:
        return {
            **_unavailable("embedding_vector_dimension_mismatch"),
            "success": False,
            "expected_dim": EMBEDDING_VECTOR_DIM,
            "actual_dim": len(embedding_vector),
        }
    role = (actor_role or "owner").strip().lower()
    sk = (subject_key or "owner").strip()
    sal = float(salience) if salience is not None else float(importance)
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if embedding_vector is not None:
            cursor.execute(
                """
                INSERT INTO neena_memories (
                    memory_type, content, owner_confirmed, importance, source, retention,
                    sensitivity_level, expires_at, embedding_model, embedding_vector, metadata_json,
                    actor_role, subject_key, salience, recall_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::halfvec, %s::jsonb, %s, %s, %s, 0)
                RETURNING *
                """,
                (
                    memory_type,
                    content,
                    owner_confirmed,
                    int(importance),
                    source,
                    retention,
                    sensitivity_level,
                    expires_at,
                    embedding_model,
                    _vector_literal(embedding_vector),
                    _metadata_json(metadata),
                    role,
                    sk,
                    sal,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO neena_memories (
                    memory_type, content, owner_confirmed, importance, source, retention,
                    sensitivity_level, expires_at, embedding_model, metadata_json,
                    actor_role, subject_key, salience, recall_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, 0)
                RETURNING *
                """,
                (
                    memory_type,
                    content,
                    owner_confirmed,
                    int(importance),
                    source,
                    retention,
                    sensitivity_level,
                    expires_at,
                    embedding_model,
                    _metadata_json(metadata),
                    role,
                    sk,
                    sal,
                ),
            )
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "memory": _decode_row(dict(row))}
    except Exception as exc:
        logger.warning("create_memory_pg failed: %s", type(exc).__name__)
        return {**_unavailable("create_memory_failed", error_type=type(exc).__name__), "success": False}


def find_memory_pg_by_dedupe_key(write_dedupe_key: str) -> dict[str, Any]:
    """Return existing owner-confirmed memory with the same write dedupe key."""
    base = is_postgres_available()
    if not base.get("available") or not write_dedupe_key:
        return {**base, "memory": None}
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT * FROM neena_memories
            WHERE (metadata_json->>'write_dedupe_key') = %s
              AND owner_confirmed = TRUE
              AND retention != 'blocked'
            ORDER BY id DESC
            LIMIT 1
            """,
            (write_dedupe_key,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"success": True, "memory": _decode_row(dict(row) if row else None)}
    except Exception as exc:
        return {**_unavailable("find_memory_failed", error_type=type(exc).__name__), "memory": None}


def create_memory_pg_idempotent(
    write_dedupe_key: str,
    memory_type: str,
    content: str,
    owner_confirmed: bool,
    importance: int = 1,
    source: str = "owner_message",
    retention: str = "permanent",
    sensitivity_level: str = "normal",
    expires_at: str | None = None,
    metadata: dict | None = None,
    embedding_model: str | None = None,
    embedding_vector: list[float] | None = None,
    actor_role: str = "owner",
    subject_key: str = "owner",
    salience: float | None = None,
) -> dict[str, Any]:
    """Create PG memory once per write_dedupe_key (safe on approval retries)."""
    existing = find_memory_pg_by_dedupe_key(write_dedupe_key)
    if existing.get("memory"):
        return {"success": True, "memory": existing["memory"], "deduped": True}

    merged_meta = dict(metadata or {})
    merged_meta["write_dedupe_key"] = write_dedupe_key
    merged_meta.setdefault("write_backend", "postgres_primary")
    if embedding_model:
        merged_meta["embedding_model"] = embedding_model

    result = create_memory_pg(
        memory_type=memory_type,
        content=content,
        owner_confirmed=owner_confirmed,
        importance=importance,
        source=source,
        retention=retention,
        sensitivity_level=sensitivity_level,
        expires_at=expires_at,
        metadata=merged_meta,
        embedding_model=embedding_model,
        embedding_vector=embedding_vector,
        actor_role=actor_role,
        subject_key=subject_key,
        salience=salience,
    )
    if result.get("success"):
        result["deduped"] = False
    return result


def search_memories_by_subject_pg(
    *,
    actor_role: str,
    subject_key: str,
    query: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "memories": []}
    role = (actor_role or "owner").strip().lower()
    sk = (subject_key or "owner").strip()
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT *
            FROM neena_memories
            WHERE owner_confirmed = TRUE
              AND retention != 'blocked'
              AND (expires_at IS NULL OR expires_at > NOW())
              AND actor_role = %s
              AND subject_key = %s
            ORDER BY salience DESC NULLS LAST, updated_at DESC, id DESC
            LIMIT %s
            """,
            (role, sk, int(limit) * 3),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        conn.close()
        all_items = []
        q = (query or "").strip().lower()
        for row in rows:
            item = _decode_row(dict(row))
            if not item:
                continue
            item["_memory_backend"] = "postgres_subject"
            all_items.append(item)

        memories: list = []
        if q:
            filtered = [
                i
                for i in all_items
                if q in (i.get("content") or "").lower() or q in (i.get("memory_type") or "")
            ]
            if role == "customer":
                name_hits = [i for i in all_items if (i.get("memory_type") or "") == "customer_name"]
                merged = []
                seen_ids: set = set()
                for i in name_hits + (filtered if filtered else all_items):
                    mid = i.get("id")
                    if mid in seen_ids:
                        continue
                    if mid is not None:
                        seen_ids.add(mid)
                    merged.append(i)
                memories = merged[: int(limit)]
            else:
                memories = (filtered if filtered else all_items)[: int(limit)]
        else:
            memories = all_items[: int(limit)]
        return {"success": True, "memories": memories}
    except Exception as exc:
        return {**_unavailable("subject_search_failed", error_type=type(exc).__name__), "memories": []}


def bump_memory_recall_pg(memory_ids: list[int]) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available") or not memory_ids:
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        for mid in memory_ids:
            cursor.execute(
                """
                UPDATE neena_memories
                SET last_recalled_at = NOW(),
                    recall_count = COALESCE(recall_count, 0) + 1,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (int(mid),),
            )
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "updated": len(memory_ids)}
    except Exception as exc:
        return {**_unavailable("bump_recall_failed", error_type=type(exc).__name__), "success": False}


def update_memory_metadata_pg(memory_id: int, metadata_patch: dict) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT metadata_json FROM neena_memories WHERE id = %s", (memory_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return {"success": False, "reason": "memory_not_found"}
        current = row.get("metadata_json") or {}
        if isinstance(current, str):
            try:
                current = json.loads(current)
            except Exception:
                current = {}
        merged = {**current, **(metadata_patch or {})}
        cursor.execute(
            """
            UPDATE neena_memories
            SET metadata_json = %s::jsonb, updated_at = NOW()
            WHERE id = %s
            """,
            (_metadata_json(merged), memory_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "memory_id": memory_id}
    except Exception as exc:
        return {**_unavailable("update_metadata_failed", error_type=type(exc).__name__), "success": False}


def get_memory_pg(memory_id: int) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "memory": None}
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM neena_memories WHERE id = %s", (memory_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"success": True, "memory": _decode_row(dict(row) if row else None)}
    except Exception as exc:
        return {**_unavailable("get_memory_failed", error_type=type(exc).__name__), "memory": None}


def list_active_memories_pg(
    limit: int = 50,
    memory_type: str | None = None,
    *,
    actor_role: str | None = "owner",
    subject_key: str | None = "owner",
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "memories": []}
    params: list[Any] = []
    where = [
        "owner_confirmed = TRUE",
        "retention != 'blocked'",
        "(expires_at IS NULL OR expires_at > NOW())",
    ]
    if memory_type:
        where.append("memory_type = %s")
        params.append(memory_type)
    if actor_role:
        where.append("actor_role = %s")
        params.append((actor_role or "").strip().lower())
    if subject_key:
        where.append("subject_key = %s")
        params.append((subject_key or "").strip())
    params.append(int(limit))
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            SELECT * FROM neena_memories
            WHERE {' AND '.join(where)}
            ORDER BY importance DESC, updated_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {
            "success": True,
            "memories": [_decode_row(dict(row)) for row in rows if row],
        }
    except Exception as exc:
        return {**_unavailable("list_memories_failed", error_type=type(exc).__name__), "memories": []}


def search_memories_keyword_pg(
    query: str,
    limit: int = 5,
    *,
    actor_role: str | None = None,
    subject_key: str | None = None,
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "memories": []}
    clean_query = (query or "").strip().lower()
    if not clean_query:
        return {"success": True, "memories": [], "match_type": "keyword"}
    where = [
        "owner_confirmed = TRUE",
        "retention != 'blocked'",
        "(expires_at IS NULL OR expires_at > NOW())",
        "("
        "LOWER(content) LIKE %s"
        " OR LOWER(memory_type) LIKE %s"
        " OR LOWER(source) LIKE %s"
        ")",
    ]
    params: list[Any] = [f"%{clean_query}%", f"%{clean_query}%", f"%{clean_query}%"]
    if actor_role:
        where.append("actor_role = %s")
        params.append((actor_role or "").strip().lower())
    if subject_key:
        where.append("subject_key = %s")
        params.append((subject_key or "").strip())
    params.append(int(limit))
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            SELECT * FROM neena_memories
            WHERE {' AND '.join(where)}
            ORDER BY importance DESC, updated_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        memories = [_decode_row(dict(row)) for row in rows if row]
        for item in memories:
            if item:
                item["match_type"] = "keyword"
        return {"success": True, "memories": memories}
    except Exception as exc:
        return {**_unavailable("keyword_search_failed", error_type=type(exc).__name__), "memories": []}


def search_memories_vector_pg(
    query_vector: list[float],
    top_k: int = 3,
    *,
    actor_role: str | None = None,
    subject_key: str | None = None,
) -> dict[str, Any]:
    pgvec = is_pgvector_available()
    if not pgvec.get("available"):
        return {**pgvec, "memories": []}
    if not query_vector or len(query_vector) != EMBEDDING_VECTOR_DIM:
        return {
            **_unavailable("embedding_vector_dimension_mismatch"),
            "memories": [],
            "expected_dim": EMBEDDING_VECTOR_DIM,
            "actual_dim": len(query_vector or []),
        }
    vector_literal = _vector_literal(query_vector)
    where = [
        "owner_confirmed = TRUE",
        "retention != 'blocked'",
        "(expires_at IS NULL OR expires_at > NOW())",
        "embedding_vector IS NOT NULL",
    ]
    params: list[Any] = [vector_literal]
    if actor_role:
        where.append("actor_role = %s")
        params.append((actor_role or "").strip().lower())
    if subject_key:
        where.append("subject_key = %s")
        params.append((subject_key or "").strip())
    params.extend([vector_literal, int(top_k)])
    try:
        conn = _connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            SELECT
                   id,
                   memory_type,
                   content,
                   owner_confirmed,
                   importance,
                   source,
                   retention,
                   sensitivity_level,
                   created_at,
                   updated_at,
                   expires_at,
                   embedding_model,
                   metadata_json,
                   actor_role,
                   subject_key,
                   (embedding_vector <=> %s::halfvec) AS distance
            FROM neena_memories
            WHERE {' AND '.join(where)}
            ORDER BY embedding_vector <=> %s::halfvec, id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        memories = []
        for row in rows:
            item = _decode_row(dict(row))
            if item:
                item["match_type"] = "vector"
                memories.append(item)
        return {"success": True, "memories": memories}
    except Exception as exc:
        return {**_unavailable("vector_search_failed", error_type=type(exc).__name__), "memories": []}


def update_memory_embedding_pg(
    memory_id: int,
    embedding_model: str,
    embedding_vector: list[float],
) -> dict[str, Any]:
    if len(embedding_vector) != EMBEDDING_VECTOR_DIM:
        return {
            **_unavailable("embedding_vector_dimension_mismatch"),
            "success": False,
            "expected_dim": EMBEDDING_VECTOR_DIM,
            "actual_dim": len(embedding_vector),
        }
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE neena_memories
            SET embedding_model = %s,
                embedding_vector = %s::halfvec,
                updated_at = NOW()
            WHERE id = %s
            """,
            (embedding_model, _vector_literal(embedding_vector), memory_id),
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": affected > 0, "memory_id": memory_id}
    except Exception as exc:
        return {**_unavailable("update_embedding_failed", error_type=type(exc).__name__), "success": False}


def log_memory_event_pg(
    memory_id: int | None,
    event_type: str,
    user_message: str | None = None,
    assistant_response: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO neena_memory_events (
                memory_id, event_type, user_message, assistant_response, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (memory_id, event_type, user_message, assistant_response, _metadata_json(metadata)),
        )
        event_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "event_id": event_id}
    except Exception as exc:
        return {**_unavailable("log_event_failed", error_type=type(exc).__name__), "success": False}


def expire_memory_pg(memory_id: int) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE neena_memories
            SET expires_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (memory_id,),
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": affected > 0, "memory_id": memory_id}
    except Exception as exc:
        return {**_unavailable("expire_memory_failed", error_type=type(exc).__name__), "success": False}


def update_memory_content_pg(memory_id: int, new_content: str) -> dict[str, Any]:
    """Replace a memory's content text in place (embedding is refreshed separately)."""
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE neena_memories SET content = %s, updated_at = NOW() WHERE id = %s",
            (new_content, memory_id),
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": affected > 0, "memory_id": memory_id}
    except Exception as exc:
        return {**_unavailable("update_content_failed", error_type=type(exc).__name__), "success": False}


def create_activity_log_pg(
    event_type: str,
    actor: str = "system",
    message: str | None = None,
    tool_name: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    base = is_postgres_available()
    if not base.get("available"):
        return {**base, "success": False}
    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO neena_activity_logs (
                event_type, actor, message, tool_name, status, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (event_type, actor, message, tool_name, status, _metadata_json(metadata)),
        )
        log_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "log_id": log_id}
    except Exception as exc:
        return {**_unavailable("activity_log_failed", error_type=type(exc).__name__), "success": False}


__all__ = [
    "SHADOW_MODE",
    "LIVE_MEMORY_BACKEND",
    "EMBEDDING_VECTOR_DIM",
    "is_postgres_available",
    "is_pgvector_available",
    "ensure_postgres_memory_schema",
    "create_memory_pg",
    "find_memory_pg_by_dedupe_key",
    "create_memory_pg_idempotent",
    "search_memories_by_subject_pg",
    "bump_memory_recall_pg",
    "update_memory_metadata_pg",
    "get_memory_pg",
    "list_active_memories_pg",
    "search_memories_keyword_pg",
    "search_memories_vector_pg",
    "update_memory_embedding_pg",
    "update_memory_content_pg",
    "log_memory_event_pg",
    "expire_memory_pg",
    "create_activity_log_pg",
]

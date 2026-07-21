"""
M2-A3: Shadow-only SQLite -> PostgreSQL (pgvector) migration + embedding backfill.

Hard rules:
- Does NOT switch live memory backend (SQLite remains live).
- Does NOT delete or modify SQLite data.
- Writes ONLY to PostgreSQL shadow tables defined by backend/migrations/postgres_memory_schema.sql.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Iterable

import psycopg2
import psycopg2.extras

# Import backend modules by adding repo root/backend to sys.path when run from repo root.
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(REPO_ROOT, "backend"))

import database as sqlite_db  # noqa: E402
from services.memory.embedding_provider import PRIMARY_EMBEDDING_MODEL, embed_text  # noqa: E402
from services.memory.pg_repository import (  # noqa: E402
    EMBEDDING_VECTOR_DIM,
    ensure_postgres_memory_schema,
)


def _pg_cfg() -> dict[str, Any]:
    return {
        "host": os.environ.get("NEENA_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("NEENA_PG_PORT", "5432")),
        "dbname": os.environ.get("NEENA_PG_DB", "neena_memory_shadow"),
        "user": os.environ.get("NEENA_PG_USER", "neena_shadow"),
        "password": os.environ.get("NEENA_PG_PASSWORD", "neena_shadow_dev"),
        "connect_timeout": 5,
    }


def _pg_connect():
    return psycopg2.connect(**_pg_cfg())


def _json_load(s: str | None) -> dict[str, Any]:
    if not s:
        return {}
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _json_dump(d: dict[str, Any]) -> str:
    return json.dumps(d, ensure_ascii=False)


def _iter_sqlite_confirmed_active_permanent() -> Iterable[dict[str, Any]]:
    """
    Mirrors SQLite live filter:
      owner_confirmed=1 AND retention!='blocked' AND not expired
    Plus: only retention='permanent' (per M2-A3 requirement).
    """
    conn = sqlite_db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM neena_memories
        WHERE owner_confirmed = 1
          AND retention = 'permanent'
          AND retention != 'blocked'
          AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        ORDER BY id ASC
        """
    )
    rows = cur.fetchall() or []
    conn.close()
    for row in rows:
        yield dict(row)


def _sqlite_events_for_memory_ids(memory_ids: list[int]) -> list[dict[str, Any]]:
    if not memory_ids:
        return []
    conn = sqlite_db.get_db_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in memory_ids)
    cur.execute(
        f"""
        SELECT *
        FROM neena_memory_events
        WHERE memory_id IN ({placeholders})
        ORDER BY id ASC
        """,
        memory_ids,
    )
    rows = cur.fetchall() or []
    conn.close()
    return [dict(r) for r in rows]


def migrate_sqlite_to_postgres_shadow(limit: int | None = None) -> dict[str, Any]:
    ensure_postgres_memory_schema()

    migrated = 0
    skipped_existing = 0
    attempted = 0
    sqlite_ids: list[int] = []

    pg = _pg_connect()
    pg.autocommit = True
    cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        for item in _iter_sqlite_confirmed_active_permanent():
            attempted += 1
            if limit is not None and migrated >= int(limit):
                break

            sqlite_id = int(item["id"])
            sqlite_ids.append(sqlite_id)

            # Dedup: if we already migrated this SQLite id, skip.
            cur.execute(
                """
                SELECT id
                FROM neena_memories
                WHERE (metadata_json->>'sqlite_memory_id') = %s
                LIMIT 1
                """,
                (str(sqlite_id),),
            )
            if cur.fetchone():
                skipped_existing += 1
                continue

            sqlite_meta = _json_load(item.get("metadata_json"))
            merged_meta = {
                **sqlite_meta,
                "migrated_from_sqlite": True,
                "sqlite_memory_id": sqlite_id,
            }

            # Preserve timestamps where possible (SQLite stores TEXT timestamps).
            created_at = item.get("created_at")
            updated_at = item.get("updated_at")
            expires_at = item.get("expires_at")

            cur.execute(
                """
                INSERT INTO neena_memories (
                    memory_type, content, owner_confirmed, importance, source, retention,
                    sensitivity_level, created_at, updated_at, expires_at,
                    embedding_model, embedding_vector, metadata_json
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    NULL, NULL, %s::jsonb
                )
                RETURNING id
                """,
                (
                    item.get("memory_type"),
                    item.get("content"),
                    True,
                    int(item.get("importance") or 1),
                    item.get("source") or "owner_message",
                    item.get("retention") or "permanent",
                    item.get("sensitivity_level") or "normal",
                    created_at,
                    updated_at,
                    expires_at,
                    _json_dump(merged_meta),
                ),
            )
            _ = cur.fetchone()
            migrated += 1
    finally:
        cur.close()
        pg.close()

    # Migrate events (shadow visibility only). This does not affect live behavior.
    events_migrated = 0
    if sqlite_ids:
        events = _sqlite_events_for_memory_ids(sqlite_ids)
        pg = _pg_connect()
        pg.autocommit = True
        cur = pg.cursor()
        try:
            for ev in events:
                # Map by sqlite_memory_id lookup.
                cur.execute(
                    "SELECT id FROM neena_memories WHERE (metadata_json->>'sqlite_memory_id')=%s LIMIT 1",
                    (str(ev.get("memory_id")),),
                )
                row = cur.fetchone()
                if not row:
                    continue
                pg_memory_id = int(row[0])

                ev_meta = _json_load(ev.get("metadata_json"))
                ev_meta = {
                    **ev_meta,
                    "migrated_from_sqlite": True,
                    "sqlite_event_id": int(ev.get("id")),
                }
                cur.execute(
                    """
                    INSERT INTO neena_memory_events (
                        memory_id, event_type, user_message, assistant_response, created_at, metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        pg_memory_id,
                        ev.get("event_type"),
                        ev.get("user_message"),
                        ev.get("assistant_response"),
                        ev.get("created_at"),
                        _json_dump(ev_meta),
                    ),
                )
                events_migrated += 1
        finally:
            cur.close()
            pg.close()

    return {
        "attempted_sqlite_memories": attempted,
        "migrated_postgres_memories": migrated,
        "skipped_existing": skipped_existing,
        "migrated_events": events_migrated,
    }


def backfill_embeddings_shadow(limit: int | None = None) -> dict[str, Any]:
    ensure_postgres_memory_schema()

    pg = _pg_connect()
    pg.autocommit = True
    cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    selected: list[dict[str, Any]] = []
    cur.execute(
        """
        SELECT id, content
        FROM neena_memories
        WHERE owner_confirmed = TRUE
          AND retention != 'blocked'
          AND (expires_at IS NULL OR expires_at > NOW())
          AND embedding_vector IS NULL
        ORDER BY id ASC
        """
    )
    rows = cur.fetchall() or []
    for r in rows:
        selected.append(dict(r))

    updated = 0
    failed = 0
    attempted = 0

    try:
        for row in selected:
            if limit is not None and updated >= int(limit):
                break
            attempted += 1

            embed = embed_text(str(row.get("content") or ""))
            if embed.get("status") != "success":
                failed += 1
                continue
            vec = embed.get("vector") or []
            if len(vec) != EMBEDDING_VECTOR_DIM:
                failed += 1
                continue

            # Store in halfvec(3072).
            vec_literal = "[" + ",".join(f"{float(v):.8f}" for v in vec) + "]"
            cur.execute(
                """
                UPDATE neena_memories
                SET embedding_model = %s,
                    embedding_vector = %s::halfvec,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (PRIMARY_EMBEDDING_MODEL, vec_literal, int(row["id"])),
            )
            updated += 1

            # Optional: record an event (shadow-only table).
            cur.execute(
                """
                INSERT INTO neena_memory_events (memory_id, event_type, created_at, metadata_json)
                VALUES (%s, %s, NOW(), %s::jsonb)
                """,
                (
                    int(row["id"]),
                    "embedding_backfilled",
                    _json_dump({"model": PRIMARY_EMBEDDING_MODEL, "dim": len(vec), "shadow": True}),
                ),
            )
    finally:
        cur.close()
        pg.close()

    return {
        "attempted": attempted,
        "backfilled": updated,
        "failed": failed,
        "model": PRIMARY_EMBEDDING_MODEL,
        "dim": EMBEDDING_VECTOR_DIM,
    }


def semantic_retrieval_probe(query: str, top_k: int = 3) -> dict[str, Any]:
    """
    Shadow-only semantic retrieval proof:
    - embed query with gemini-embedding-2
    - search in PG with pgvector halfvec
    """
    ensure_postgres_memory_schema()
    embed = embed_text(query)
    if embed.get("status") != "success":
        return {"success": False, "stage": "embed", "error": embed.get("error") or embed.get("status")}
    vec = embed.get("vector") or []
    if len(vec) != EMBEDDING_VECTOR_DIM:
        return {"success": False, "stage": "embed", "error": f"vector_len={len(vec)} expected={EMBEDDING_VECTOR_DIM}"}

    vec_literal = "[" + ",".join(f"{float(v):.8f}" for v in vec) + "]"

    pg = _pg_connect()
    pg.autocommit = True
    cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id, memory_type, content, embedding_model,
                   (embedding_vector <=> %s::halfvec) AS distance
            FROM neena_memories
            WHERE owner_confirmed = TRUE
              AND retention != 'blocked'
              AND (expires_at IS NULL OR expires_at > NOW())
              AND embedding_vector IS NOT NULL
            ORDER BY embedding_vector <=> %s::halfvec
            LIMIT %s
            """,
            (vec_literal, vec_literal, int(top_k)),
        )
        rows = [dict(r) for r in (cur.fetchall() or [])]
    finally:
        cur.close()
        pg.close()

    return {
        "success": True,
        "backend": "postgres_shadow",
        "search": "pgvector",
        "model": PRIMARY_EMBEDDING_MODEL,
        "hit_count": len(rows),
        "hits": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--migrate", action="store_true", help="Migrate confirmed active permanent SQLite memories to PG shadow")
    ap.add_argument("--backfill", action="store_true", help="Backfill missing embeddings into PG shadow using gemini-embedding-2")
    ap.add_argument("--probe", action="store_true", help="Run semantic retrieval probe (shadow)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--query", type=str, default="meri radio script wali style kya hai?")
    args = ap.parse_args()

    if not (args.migrate or args.backfill or args.probe):
        args.migrate = True
        args.backfill = True
        args.probe = True

    out: dict[str, Any] = {"ts": datetime.utcnow().isoformat() + "Z"}

    if args.migrate:
        out["migration"] = migrate_sqlite_to_postgres_shadow(limit=args.limit)
    if args.backfill:
        out["backfill"] = backfill_embeddings_shadow(limit=args.limit)
    if args.probe:
        out["probe"] = semantic_retrieval_probe(args.query, top_k=3)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


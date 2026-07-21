import json
import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

KEYWORD_STOPWORDS = {
    "karo",
    "kro",
    "karna",
    "hai",
    "hain",
    "kya",
    "meri",
    "mera",
    "mere",
    "ise",
    "isko",
}


MEMORY_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS neena_memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_type TEXT NOT NULL,
        content TEXT NOT NULL,
        owner_confirmed INTEGER NOT NULL DEFAULT 0,
        importance INTEGER NOT NULL DEFAULT 1,
        source TEXT NOT NULL DEFAULT 'owner_message',
        retention TEXT NOT NULL DEFAULT 'permanent',
        sensitivity_level TEXT NOT NULL DEFAULT 'normal',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        embedding_model TEXT,
        embedding_vector TEXT,
        metadata_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS neena_memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER,
        event_type TEXT NOT NULL,
        user_message TEXT,
        assistant_response TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        metadata_json TEXT,
        FOREIGN KEY(memory_id) REFERENCES neena_memories(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_neena_memories_type ON neena_memories(memory_type)",
    "CREATE INDEX IF NOT EXISTS idx_neena_memories_retention ON neena_memories(retention)",
    "CREATE INDEX IF NOT EXISTS idx_neena_memories_sensitivity ON neena_memories(sensitivity_level)",
    "CREATE INDEX IF NOT EXISTS idx_neena_memories_expires_at ON neena_memories(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_neena_memory_events_memory_id ON neena_memory_events(memory_id)",
]


def _metadata_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False)


def _decode_row(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    raw_metadata = item.get("metadata_json")
    try:
        item["metadata"] = json.loads(raw_metadata) if raw_metadata else {}
    except Exception:
        item["metadata"] = {}
    return item


def ensure_memory_schema() -> dict:
    """
    Creates only the M1 permanent memory tables/indexes if they are missing.
    Also ensures actor-scope / soft-fade columns (local one-brain Phase 1).
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    for statement in MEMORY_SCHEMA_STATEMENTS:
        cursor.execute(statement)
    _ensure_actor_scope_columns(cursor)
    conn.commit()
    conn.close()
    return {"success": True, "tables": ["neena_memories", "neena_memory_events"]}


def _table_columns(cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cursor.fetchall()}


def _ensure_actor_scope_columns(cursor) -> None:
    cols = _table_columns(cursor, "neena_memories")
    alters = [
        ("actor_role", "TEXT NOT NULL DEFAULT 'owner'"),
        ("subject_key", "TEXT NOT NULL DEFAULT 'owner'"),
        ("salience", "REAL NOT NULL DEFAULT 1"),
        ("last_recalled_at", "DATETIME"),
        ("recall_count", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for name, decl in alters:
        if name not in cols:
            cursor.execute(f"ALTER TABLE neena_memories ADD COLUMN {name} {decl}")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_neena_memories_actor_subject "
        "ON neena_memories(actor_role, subject_key)"
    )


def create_memory(
    memory_type: str,
    content: str,
    owner_confirmed: bool,
    importance: int = 1,
    source: str = "owner_message",
    retention: str = "permanent",
    sensitivity_level: str = "normal",
    expires_at: str | None = None,
    metadata: dict | None = None,
    actor_role: str = "owner",
    subject_key: str = "owner",
    salience: float | None = None,
) -> dict:
    ensure_memory_schema()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    sal = float(salience) if salience is not None else float(importance)
    cursor.execute(
        """
        INSERT INTO neena_memories (
            memory_type, content, owner_confirmed, importance, source, retention,
            sensitivity_level, expires_at, embedding_model, embedding_vector, metadata_json,
            actor_role, subject_key, salience, recall_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, 0)
        """,
        (
            memory_type,
            content,
            1 if owner_confirmed else 0,
            int(importance),
            source,
            retention,
            sensitivity_level,
            expires_at,
            _metadata_json(metadata),
            (actor_role or "owner").strip().lower(),
            (subject_key or "owner").strip(),
            sal,
        ),
    )
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_memory_by_id(memory_id)


def search_memories_by_subject(
    *,
    actor_role: str,
    subject_key: str,
    query: str = "",
    limit: int = 10,
) -> list[dict]:
    ensure_memory_schema()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    role = (actor_role or "owner").strip().lower()
    sk = (subject_key or "owner").strip()
    q = (query or "").strip().lower()
    try:
        cursor.execute(
            """
            SELECT * FROM neena_memories
            WHERE owner_confirmed = 1
              AND retention != 'blocked'
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
              AND actor_role = ?
              AND subject_key = ?
            ORDER BY salience DESC, updated_at DESC, id DESC
            LIMIT ?
            """,
            (role, sk, int(limit) * 3),
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    items = [_decode_row(r) for r in rows]
    items = [i for i in items if i]
    if q:
        filtered = [
            i
            for i in items
            if q in (i.get("content") or "").lower() or q in (i.get("memory_type") or "")
        ]
        if role == "customer":
            # Never drop durable name just because the utterance didn't match it.
            name_hits = [i for i in items if (i.get("memory_type") or "") == "customer_name"]
            merged: list[dict] = []
            seen_ids: set = set()
            for i in name_hits + (filtered if filtered else items):
                mid = i.get("id")
                if mid in seen_ids:
                    continue
                if mid is not None:
                    seen_ids.add(mid)
                merged.append(i)
            items = merged
        elif filtered:
            items = filtered
    return items[: int(limit)]


def bump_memory_recall(memory_ids: list[int]) -> None:
    if not memory_ids:
        return
    ensure_memory_schema()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    for mid in memory_ids:
        try:
            cursor.execute(
                """
                UPDATE neena_memories
                SET last_recalled_at = CURRENT_TIMESTAMP,
                    recall_count = COALESCE(recall_count, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(mid),),
            )
        except (sqlite3.OperationalError, TypeError, ValueError):
            continue
    conn.commit()
    conn.close()


def find_confirmed_memory_by_content(content: str) -> dict | None:
    """Find an owner-confirmed permanent memory with exact content (mirror dedupe)."""
    clean = (content or "").strip()
    if not clean:
        return None
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT * FROM neena_memories
            WHERE content = ?
              AND owner_confirmed = 1
              AND retention = 'permanent'
            ORDER BY id DESC
            LIMIT 1
            """,
            (clean,),
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    return _decode_row(row)


def get_memory_by_id(memory_id: int) -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM neena_memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    return _decode_row(row)


def list_active_memories(
    limit: int = 50,
    memory_type: str | None = None,
    *,
    actor_role: str | None = "owner",
    subject_key: str | None = "owner",
) -> list[dict]:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    params: list = []
    where = [
        "owner_confirmed = 1",
        "retention != 'blocked'",
        "(expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
    ]
    if memory_type:
        where.append("memory_type = ?")
        params.append(memory_type)
    if actor_role:
        where.append("actor_role = ?")
        params.append((actor_role or "").strip().lower())
    if subject_key:
        where.append("subject_key = ?")
        params.append((subject_key or "").strip())
    params.append(int(limit))
    try:
        cursor.execute(
            f"""
            SELECT * FROM neena_memories
            WHERE {' AND '.join(where)}
            ORDER BY importance DESC, updated_at DESC, id DESC
            LIMIT ?
            """,
            params,
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [_decode_row(row) for row in rows if row]


def search_memories_keyword(
    query: str,
    limit: int = 5,
    *,
    actor_role: str | None = "owner",
    subject_key: str | None = "owner",
) -> list[dict]:
    clean_query = (query or "").strip().lower()
    if not clean_query:
        return []
    tokens = [
        token
        for token in clean_query.replace(",", " ").split()
        if len(token) > 2 and token not in KEYWORD_STOPWORDS
    ]
    if not tokens:
        tokens = [clean_query]

    matches = []
    for item in list_active_memories(
        limit=100, actor_role=actor_role, subject_key=subject_key
    ):
        haystack = " ".join(
            [
                str(item.get("content") or ""),
                str(item.get("memory_type") or ""),
                str(item.get("source") or ""),
                str(item.get("metadata_json") or ""),
            ]
        ).lower()
        if any(token in haystack for token in tokens):
            item["match_type"] = "keyword"
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def log_memory_event(
    memory_id: int | None,
    event_type: str,
    user_message: str | None = None,
    assistant_response: str | None = None,
    metadata: dict | None = None,
) -> dict:
    ensure_memory_schema()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO neena_memory_events (
            memory_id, event_type, user_message, assistant_response, metadata_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (memory_id, event_type, user_message, assistant_response, _metadata_json(metadata)),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "event_id": event_id}


def correct_memory_content_if_exact(old_content: str, new_content: str) -> dict:
    """
    Corrects rows only when their content exactly matches old_content.
    Intended for narrow local data hygiene fixes; does not alter schema.
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM neena_memories WHERE content = ?",
            (old_content,),
        )
        memory_ids = [row["id"] for row in cursor.fetchall()]
        if memory_ids:
            cursor.execute(
                """
                UPDATE neena_memories
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE content = ?
                """,
                (new_content, old_content),
            )
            conn.commit()
    except sqlite3.OperationalError as exc:
        conn.close()
        return {"success": False, "updated_count": 0, "memory_ids": [], "error": str(exc)}
    conn.close()

    for memory_id in memory_ids:
        log_memory_event(
            memory_id=memory_id,
            event_type="corrected_candidate_trim",
            metadata={"old_content": old_content, "new_content": new_content},
        )

    return {"success": True, "updated_count": len(memory_ids), "memory_ids": memory_ids}


def expire_memory(memory_id: int) -> dict:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE neena_memories
            SET expires_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (memory_id,),
        )
        affected = cursor.rowcount
        conn.commit()
    except sqlite3.OperationalError as exc:
        affected = 0
        error = str(exc)
    else:
        error = None
    conn.close()
    return {"success": affected > 0, "memory_id": memory_id, "error": error}

"""Data layer for cockpit background jobs (SQLite).

Rule 2/3: this module owns ALL SQL for the `cockpit_jobs` table. Business logic
and orchestration live in `cockpit_job_service.py`, which imports these helpers.
Keep SQL here only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import database as db

JOB_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_cockpit_jobs_table() -> None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cockpit_jobs (
            job_id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            progress_message TEXT,
            owner_message TEXT,
            safe_details_json TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            error_summary TEXT,
            gemini_calls INTEGER DEFAULT 0,
            latency_ms INTEGER
        )
        """
    )
    # M5 migration: owner_seen flag for server-side completion delivery.
    try:
        cursor.execute("ALTER TABLE cockpit_jobs ADD COLUMN owner_seen INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # column already exists
    conn.commit()
    conn.close()


def _row_to_dict(row) -> dict[str, Any]:
    if not row:
        return {}
    data = dict(row)
    for key in ("safe_details_json", "payload_json"):
        raw = data.pop(key, None)
        parsed_key = key.replace("_json", "")
        if raw:
            try:
                data[parsed_key] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                data[parsed_key] = {}
        else:
            data[parsed_key] = {}
    return data


def insert_job(job_id: str, action: str, payload: dict[str, Any] | None) -> None:
    ensure_cockpit_jobs_table()
    now = _utc_now()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cockpit_jobs (
            job_id, action, status, progress_message, payload_json,
            created_at, updated_at, gemini_calls
        ) VALUES (?, ?, 'queued', ?, ?, ?, ?, 0)
        """,
        (job_id, action, "Queued", json.dumps(payload or {}), now, now),
    )
    conn.commit()
    conn.close()


def mark_running(job_id: str, progress_message: str | None = None) -> None:
    now = _utc_now()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE cockpit_jobs
        SET status = 'running', progress_message = COALESCE(?, progress_message), updated_at = ?
        WHERE job_id = ?
        """,
        (progress_message, now, job_id),
    )
    conn.commit()
    conn.close()


def update_progress(job_id: str, message: str, details: dict[str, Any] | None = None) -> None:
    now = _utc_now()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    if details is not None:
        cursor.execute(
            """
            UPDATE cockpit_jobs
            SET progress_message = ?, safe_details_json = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (message, json.dumps(details), now, job_id),
        )
    else:
        cursor.execute(
            """
            UPDATE cockpit_jobs
            SET progress_message = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (message, now, job_id),
        )
    conn.commit()
    conn.close()


def mark_succeeded(
    job_id: str,
    owner_message: str,
    details: dict[str, Any] | None = None,
    *,
    latency_ms: int | None = None,
) -> None:
    now = _utc_now()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE cockpit_jobs
        SET status = 'succeeded', owner_message = ?, safe_details_json = COALESCE(?, safe_details_json),
            updated_at = ?, finished_at = ?, latency_ms = COALESCE(?, latency_ms), gemini_calls = 0
        WHERE job_id = ?
        """,
        (
            owner_message,
            json.dumps(details) if details is not None else None,
            now,
            now,
            latency_ms,
            job_id,
        ),
    )
    conn.commit()
    conn.close()


def mark_failed(
    job_id: str,
    error_summary: str,
    owner_message: str | None = None,
    *,
    latency_ms: int | None = None,
) -> None:
    now = _utc_now()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE cockpit_jobs
        SET status = 'failed', error_summary = ?, owner_message = COALESCE(?, owner_message),
            updated_at = ?, finished_at = ?, latency_ms = COALESCE(?, latency_ms), gemini_calls = 0
        WHERE job_id = ?
        """,
        (error_summary, owner_message, now, now, latency_ms, job_id),
    )
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    ensure_cockpit_jobs_table()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cockpit_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    data = _row_to_dict(row)
    return {
        "ok": True,
        "job_id": data.get("job_id"),
        "action": data.get("action"),
        "status": data.get("status"),
        "progress_message": data.get("progress_message"),
        "owner_message": data.get("owner_message"),
        "safe_details": data.get("safe_details") or {},
        "error_summary": data.get("error_summary"),
        "gemini_calls": int(data.get("gemini_calls") or 0),
        "latency_ms": data.get("latency_ms"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "finished_at": data.get("finished_at"),
    }


def mark_owner_seen(job_ids: list[str]) -> None:
    """Mark finished jobs as delivered to the owner (web or WhatsApp)."""
    if not job_ids:
        return
    ensure_cockpit_jobs_table()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in job_ids)
    cursor.execute(
        f"UPDATE cockpit_jobs SET owner_seen = 1 WHERE job_id IN ({placeholders})",
        tuple(job_ids),
    )
    conn.commit()
    conn.close()


def list_unseen_finished_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """Finished (succeeded/failed) jobs the owner has not yet been shown."""
    ensure_cockpit_jobs_table()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT job_id, action, status, owner_message, error_summary, finished_at
        FROM cockpit_jobs
        WHERE status IN ('succeeded', 'failed')
          AND COALESCE(owner_seen, 0) = 0
          AND owner_message IS NOT NULL
        ORDER BY finished_at ASC LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_active_jobs(limit: int = 10) -> list[dict[str, Any]]:
    ensure_cockpit_jobs_table()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT job_id, action, status, progress_message, created_at, updated_at
        FROM cockpit_jobs
        WHERE status IN ('queued', 'running')
        ORDER BY created_at DESC LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def find_active_job_for_action(action: str) -> str | None:
    ensure_cockpit_jobs_table()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT job_id FROM cockpit_jobs
        WHERE action = ? AND status IN ('queued', 'running')
        ORDER BY created_at DESC LIMIT 1
        """,
        (action,),
    )
    row = cursor.fetchone()
    conn.close()
    return row["job_id"] if row else None


__all__ = [
    "JOB_STATUSES",
    "ensure_cockpit_jobs_table",
    "insert_job",
    "mark_running",
    "update_progress",
    "mark_succeeded",
    "mark_failed",
    "get_job",
    "mark_owner_seen",
    "list_unseen_finished_jobs",
    "list_active_jobs",
    "find_active_job_for_action",
]

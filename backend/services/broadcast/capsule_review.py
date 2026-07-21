"""Capsule review workflow service for script/content approval, rejection, and revisions."""
from __future__ import annotations

import logging
import database as db
from services.broadcast.capsule_service import get_capsule_by_id, list_recent_capsules

logger = logging.getLogger(__name__)


def list_recent_capsules_review(limit: int = 5) -> list[dict]:
    """Retrieves recent capsules for review."""
    return list_recent_capsules(limit=limit)


def get_capsule_review_summary(capsule_id: int | None = None) -> dict | None:
    """Gets a safe summary of a capsule for the review manager."""
    if capsule_id is not None:
        capsule = get_capsule_by_id(capsule_id)
    else:
        capsules = list_recent_capsules(limit=1)
        capsule = capsules[0] if capsules else None

    if not capsule:
        return None

    return {
        "id": capsule.get("id"),
        "title": capsule.get("title"),
        "status": capsule.get("status"),
        "approval_status": capsule.get("approval_status"),
        "audio_status": capsule.get("audio_status"),
        "broadcast_ready": bool(capsule.get("broadcast_ready")),
        "azuracast_status": capsule.get("azuracast_status") or "blocked",
        "script_text": capsule.get("script_text"),
        "reject_reason": capsule.get("reject_reason"),
    }


def mark_capsule_script_approved(capsule_id: int) -> dict | None:
    """Marks capsule script as approved without setting broadcast readiness or triggering audio."""
    logger.info("[CAPSULE_REVIEW] Script approved for capsule %s", capsule_id)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET status = 'approved', approval_status = 'approved',
            approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (capsule_id,)
    )
    conn.commit()
    conn.close()
    return get_capsule_by_id(capsule_id)


def mark_capsule_script_rejected(capsule_id: int, reason: str | None = None) -> dict | None:
    """Marks capsule script as rejected."""
    logger.info("[CAPSULE_REVIEW] Script rejected for capsule %s, reason: %s", capsule_id, reason)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET status = 'rejected', approval_status = 'rejected',
            rejected_at = CURRENT_TIMESTAMP, reject_reason = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (reason, capsule_id)
    )
    conn.commit()
    conn.close()
    return get_capsule_by_id(capsule_id)


def mark_capsule_needs_revision(capsule_id: int, reason: str | None = None) -> dict | None:
    """Marks capsule script as needing revision."""
    logger.info("[CAPSULE_REVIEW] Capsule %s needs revision, reason: %s", capsule_id, reason)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET status = 'needs_revision', approval_status = 'needs_revision',
            reject_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (reason, capsule_id)
    )
    conn.commit()
    conn.close()
    return get_capsule_by_id(capsule_id)

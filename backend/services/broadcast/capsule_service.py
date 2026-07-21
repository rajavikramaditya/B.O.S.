"""Broadcast capsule foundation — track script → approval → audio → AzuraCast readiness."""
from __future__ import annotations

import json
import logging
import os
import sys
import wave
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

logger = logging.getLogger(__name__)

AUDIO_APPROVAL_BLOCKED_MESSAGE = (
    "Audio generation blocked: capsule owner approval ke bina audio ready nahi hoga."
)

AZURACAST_BLOCKED_MESSAGE = (
    "AzuraCast real push abhi implement nahi hai. "
    "Capsule approved/audio ready hone ke baad M4-A3 me enable hoga."
)

CAPSULE_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "Broadcast capsule ID {capsule_id} | Approval queue ID {approval_id} | Status: pending_review\n"
    "Audio/AzuraCast push abhi nahi hua."
)

BROADCAST_ASSET_TYPES = frozenset(
    {"show_script", "audio_ad", "news_script", "voice_capsule", "rj_intro_script", "show_plan"}
)

INTENT_CAPSULE_MAP = {
    "rj_intro": ("rj_intro", "show_script"),
    "ad_script": ("ad_script", "audio_ad"),
    "daily_show_plan": ("daily_show_plan", "show_plan"),
}


def _row_to_dict(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    if item.get("metadata_json"):
        try:
            item["metadata"] = json.loads(item["metadata_json"])
        except Exception:
            item["metadata"] = {}
    else:
        item["metadata"] = {}
    return item


def _derive_title(capsule_type: str, script_text: str) -> str:
    text = (script_text or "").strip()
    if capsule_type == "ad_script":
        for line in text.splitlines():
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
                if title:
                    return title[:120]
    if text:
        return text.splitlines()[0][:120]
    return capsule_type.replace("_", " ").title()


def get_capsule_by_id(capsule_id: int) -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM broadcast_capsules WHERE id = ?", (capsule_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def get_capsule_by_approval_queue_id(approval_queue_id: int) -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM broadcast_capsules WHERE approval_queue_id = ?", (approval_queue_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def list_recent_capsules(limit: int = 20) -> list[dict]:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM broadcast_capsules ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = [_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    out = []
    for r in rows:
        if not r:
            continue
        if (r.get("approval_status") or "").lower() == "archived":
            continue
        if (r.get("status") or "").lower() == "archived":
            continue
        out.append(enrich_capsule_for_api(r))
    return out


def archive_capsule(capsule_id: int) -> dict:
    """Owner Lab manual delete — soft-archive (hidden from lists, not hard wipe)."""
    cap = get_capsule_by_id(capsule_id)
    if not cap:
        return {"success": False, "message": f"Capsule {capsule_id} not found."}
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET approval_status = 'archived', status = 'archived',
            azuracast_status = COALESCE(azuracast_status, 'blocked')
        WHERE id = ?
        """,
        (capsule_id,),
    )
    conn.commit()
    conn.close()
    db.add_activity_log("broadcast_capsule", f"Archived broadcast capsule {capsule_id}")
    return {"success": True, "message": f"Capsule {capsule_id} archived.", "capsule_id": capsule_id}


def create_capsule_from_script(
    *,
    approval_queue_id: int,
    script_text: str,
    capsule_type: str = "unknown",
    title: str | None = None,
    source: str = "manual",
    metadata: dict | None = None,
    topic: str | None = None,
    language: str | None = None,
    tone: str | None = None,
    created_by: str | None = None,
    status: str = "pending_approval",
) -> dict:
    existing = get_capsule_by_approval_queue_id(approval_queue_id)
    if existing:
        return existing

    title = title or _derive_title(capsule_type, script_text)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Map consistent status to legacy approval_status
    legacy_approval_status = "pending"
    if status == "approved":
        legacy_approval_status = "approved"
    elif status == "rejected":
        legacy_approval_status = "rejected"

    cursor.execute(
        """
        INSERT INTO broadcast_capsules (
            approval_queue_id, capsule_type, title, script_text, source,
            audio_truth_level, approval_status, azuracast_status,
            stream_verification_status, truth_level, metadata_json,
            topic, language, tone, status, created_by, audio_status
        ) VALUES (?, ?, ?, ?, ?, 'none', ?, 'blocked', 'unknown', 'local_only', ?, ?, ?, ?, ?, ?, 'none')
        """,
        (
            approval_queue_id,
            capsule_type,
            title,
            script_text,
            source,
            legacy_approval_status,
            metadata_json,
            topic,
            language,
            tone,
            status,
            created_by,
        ),
    )
    capsule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    db.add_activity_log(
        "broadcast_capsule",
        f"Created broadcast capsule {capsule_id} (approval {approval_queue_id}, type={capsule_type}, status={status})",
    )
    logger.info("Created broadcast capsule %s for approval %s", capsule_id, approval_queue_id)
    return get_capsule_by_id(capsule_id) or {"id": capsule_id}


def queue_script_and_create_capsule(
    script_text: str,
    *,
    intent: str,
    source: str = "m3_workflow",
    metadata: dict | None = None,
) -> dict:
    """Save script to approval queue and create linked broadcast capsule."""
    capsule_type, asset_type = INTENT_CAPSULE_MAP.get(intent, ("unknown", "show_script"))
    from services.broadcast.approval_queue import queue_asset_for_review

    approval_id = queue_asset_for_review(asset_type, script_text)
    capsule = create_capsule_from_script(
        approval_queue_id=approval_id,
        script_text=script_text,
        capsule_type=capsule_type,
        source=source,
        metadata=metadata,
    )
    return {
        "approval_id": approval_id,
        "capsule_id": capsule.get("id"),
        "capsule_type": capsule_type,
        "approval_status": "pending_review",
        "audio_truth_level": "none",
        "azuracast_status": "blocked",
    }


def append_capsule_footer(reply: str, approval_id: int, capsule_id: int) -> str:
    footer = CAPSULE_FOOTER_TEMPLATE.format(capsule_id=capsule_id, approval_id=approval_id)
    if str(capsule_id) in reply and "Broadcast capsule" in reply:
        return reply
    return reply + footer


def update_capsule_approval_status(approval_queue_id: int, status: str) -> dict | None:
    mapped = {"approved": "approved", "rejected": "rejected", "pending_review": "pending"}
    legacy_status = mapped.get(status, status)
    
    canonical_status = "pending_approval"
    audio_status_clause = ""
    if status == "approved":
        canonical_status = "approved"
        audio_status_clause = ", audio_status = 'audio_pending', approved_at = CURRENT_TIMESTAMP"
    elif status == "rejected":
        canonical_status = "rejected"
        audio_status_clause = ", rejected_at = CURRENT_TIMESTAMP"
        
    conn = db.get_db_connection()
    cursor = conn.cursor()
    query = f"""
        UPDATE broadcast_capsules
        SET approval_status = ?, status = ?, updated_at = CURRENT_TIMESTAMP {audio_status_clause}
        WHERE approval_queue_id = ?
    """
    cursor.execute(query, (legacy_status, canonical_status, approval_queue_id))
    conn.commit()
    conn.close()
    return get_capsule_by_approval_queue_id(approval_queue_id)


def approve_capsule(capsule_id: int, approved_by: str | None = None) -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET status = 'approved', approval_status = 'approved',
            approved_at = CURRENT_TIMESTAMP, approved_by = ?,
            audio_status = 'audio_pending', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (approved_by, capsule_id),
    )
    conn.commit()
    conn.close()
    db.add_activity_log("broadcast_capsule", f"Approved capsule {capsule_id} by {approved_by or 'system'}")
    return get_capsule_by_id(capsule_id)


def reject_capsule(capsule_id: int, rejected_by: str | None = None, reason: str | None = None) -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET status = 'rejected', approval_status = 'rejected',
            rejected_at = CURRENT_TIMESTAMP, rejected_by = ?,
            reject_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (rejected_by, reason, capsule_id),
    )
    conn.commit()
    conn.close()
    db.add_activity_log("broadcast_capsule", f"Rejected capsule {capsule_id} by {rejected_by or 'system'}, reason: {reason}")
    return get_capsule_by_id(capsule_id)


def get_latest_capsule() -> dict | None:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM broadcast_capsules ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def get_capsules_status_summary() -> dict[str, int]:
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM broadcast_capsules GROUP BY status")
    rows = cursor.fetchall()
    conn.close()
    
    summary = {
        "draft": 0,
        "pending_approval": 0,
        "approved": 0,
        "rejected": 0,
        "audio_pending": 0,
        "audio_ready_preview": 0,
        "broadcast_blocked": 0,
        "archived": 0,
    }
    for row in rows:
        status_name = row[0]
        if status_name in summary:
            summary[status_name] = row[1]
    return summary



def link_audio_asset_to_capsule(
    approval_queue_id: int,
    audio_file_path: str,
    audio_truth_level: str,
) -> dict | None:
    truth_level = "real" if audio_truth_level == "real" else (
        "simulated" if audio_truth_level == "simulated" else "local_only"
    )
    return update_capsule_audio_status(
        approval_queue_id,
        audio_file_path,
        audio_truth_level,
        truth_level=truth_level,
    )


def update_capsule_audio_status(
    approval_queue_id: int,
    audio_file_path: str | None,
    audio_truth_level: str,
    *,
    truth_level: str | None = None,
    error_message: str | None = None,
    metadata_patch: dict | None = None,
    audio_metadata: dict | None = None,
) -> dict | None:
    capsule = get_capsule_by_approval_queue_id(approval_queue_id)
    if not capsule:
        return None
    truth = audio_truth_level if audio_truth_level in {
        "none", "real", "simulated", "failed", "local_only"
    } else "unknown"
    tl = truth_level or ("real" if truth == "real" else "simulated" if truth == "simulated" else "local_only")

    meta = dict(capsule.get("metadata") or {})
    if metadata_patch:
        meta.update(metadata_patch)

    # Status transitions according to M4-A2 corrections
    canonical_status = capsule.get("status") or "approved"
    audio_status_val = capsule.get("audio_status") or "none"
    broadcast_ready_val = 0
    production_asset_val = 0
    azuracast_status_val = capsule.get("azuracast_status") or "blocked"

    if truth == "real":
        canonical_status = "audio_ready_preview"
        audio_status_val = "real_tts_ready"
        broadcast_ready_val = 0
        production_asset_val = 1
        azuracast_status_val = "blocked_requires_owner_approval"
        meta["production_asset"] = True
        meta["broadcast_ready"] = False
        provider = meta.get("provider") or "unknown"
    elif truth == "simulated":
        canonical_status = "audio_ready_preview"
        audio_status_val = "simulated_preview"
        broadcast_ready_val = 0
        production_asset_val = 0
        azuracast_status_val = "blocked_requires_owner_approval"
        meta["production_asset"] = False
        meta["broadcast_ready"] = False
        provider = "simulated"
    elif truth == "failed":
        canonical_status = "approved"  # keep approved state
        audio_status_val = "failed"
        broadcast_ready_val = 0
        production_asset_val = 0
        provider = meta.get("provider") or "none"
    else:
        provider = meta.get("provider") or "unknown"

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET audio_file_path = ?, audio_path = ?, audio_truth_level = ?, truth_level = ?,
            error_message = ?, metadata_json = ?, audio_status = ?, status = ?,
            audio_provider = ?, audio_metadata_json = ?, broadcast_ready = ?,
            production_asset = ?, azuracast_status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE approval_queue_id = ?
        """,
        (
            audio_file_path,
            audio_file_path,
            truth,
            tl,
            error_message,
            json.dumps(meta, ensure_ascii=False),
            audio_status_val,
            canonical_status,
            provider,
            json.dumps(audio_metadata or {}, ensure_ascii=False),
            broadcast_ready_val,
            production_asset_val,
            azuracast_status_val,
            approval_queue_id,
        ),
    )
    conn.commit()
    conn.close()
    return get_capsule_by_approval_queue_id(approval_queue_id)



def validate_capsule_for_audio_generation(capsule_id: int, *, regenerate: bool = False) -> dict[str, Any]:
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return {"allowed": False, "blocked": True, "message": "Capsule not found."}

    # First generate: approved / audio_pending. Regen also allowed after preview audio exists.
    status = capsule.get("status") or "draft"
    allowed_statuses = ("approved", "audio_pending")
    if regenerate:
        allowed_statuses = ("approved", "audio_pending", "audio_ready_preview")
    if status not in allowed_statuses:
        msg = (
            f"Audio generation is blocked for capsule in state '{status}'. "
            f"Must be one of: {', '.join(allowed_statuses)}."
        )
        return {"allowed": False, "blocked": True, "message": msg}

    if not (capsule.get("script_text") or "").strip():
        return {"allowed": False, "blocked": True, "message": "Script text missing on capsule."}
    if not capsule.get("approval_queue_id"):
        return {"allowed": False, "blocked": True, "message": "No linked approval queue item."}
    return {"allowed": True, "capsule": capsule}


def _is_playable_audio_file(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        size = os.path.getsize(path)
    except OSError:
        return False
    if size < 44:
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        try:
            with wave.open(path, "rb") as wf:
                return wf.getnframes() > 0
        except Exception:
            return False
    return size > 128


def validate_capsule_for_azuracast_push(capsule_id: int) -> dict[str, Any]:
    """Production push gate — capsule/audio checks only (not AzuraCast config)."""
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return {
            "allowed": False,
            "blocked": True,
            "message": "AzuraCast blocked: capsule not found",
        }

    reasons: list[str] = []
    if capsule.get("approval_status") != "approved":
        reasons.append("capsule owner approval missing")

    audio_path = capsule.get("audio_file_path")
    if not audio_path or not os.path.exists(audio_path):
        reasons.append("playable audio file missing")
    elif not _is_playable_audio_file(audio_path):
        reasons.append("audio file empty or not playable")

    audio_truth = capsule.get("audio_truth_level") or "none"
    if audio_truth == "simulated":
        reasons.append("simulated audio cannot be sent as production broadcast")
    elif audio_truth != "real":
        reasons.append("production real audio required (audio_truth_level must be real)")

    if reasons:
        msg = "AzuraCast blocked: " + "; ".join(reasons)
        return {"allowed": False, "blocked": True, "message": msg, "reasons": reasons, "capsule": capsule}

    return {"allowed": True, "capsule": capsule}


def update_capsule_azuracast_result(
    capsule_id: int,
    *,
    azuracast_status: str,
    mode: str,
    media_id: str | None = None,
    playlist_id: str | None = None,
    truth_level: str = "local_only",
    error_message: str | None = None,
    metadata_patch: dict | None = None,
) -> dict | None:
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return None

    meta = dict(capsule.get("metadata") or {})
    if metadata_patch:
        meta.update(metadata_patch)
    meta["azuracast_push_mode"] = mode
    if media_id:
        meta["azuracast_media_id"] = media_id
    if playlist_id:
        meta["azuracast_playlist_id_used"] = playlist_id

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET azuracast_status = ?,
            azuracast_media_id = COALESCE(?, azuracast_media_id),
            azuracast_playlist_id = COALESCE(?, azuracast_playlist_id),
            truth_level = ?,
            error_message = ?,
            stream_verification_status = 'unknown',
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            azuracast_status,
            media_id,
            playlist_id,
            truth_level,
            error_message,
            json.dumps(meta, ensure_ascii=False),
            capsule_id,
        ),
    )
    conn.commit()
    conn.close()
    db.add_activity_log(
        "azuracast_push",
        f"Capsule {capsule_id} azuracast_status={azuracast_status} mode={mode}",
    )
    return enrich_capsule_for_api(get_capsule_by_id(capsule_id) or {})


def update_capsule_playback_result(
    capsule_id: int,
    *,
    playback_status: str,
    action_taken: str,
    metadata_patch: dict | None = None,
) -> dict | None:
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return None

    meta = dict(capsule.get("metadata") or {})
    if metadata_patch:
        meta.update(metadata_patch)
    meta["playback_status"] = playback_status
    meta["playback_action_taken"] = action_taken

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(meta, ensure_ascii=False), capsule_id),
    )
    conn.commit()
    conn.close()
    db.add_activity_log("playback_control", f"Capsule {capsule_id} playback_status={playback_status}")
    return enrich_capsule_for_api(get_capsule_by_id(capsule_id) or {})


def update_capsule_stream_verification(
    capsule_id: int,
    stream_verification_status: str,
    *,
    message: str | None = None,
    metadata_patch: dict | None = None,
    error_message: str | None = None,
) -> dict | None:
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return None

    meta = dict(capsule.get("metadata") or {})
    if metadata_patch:
        meta.update(metadata_patch)
    if message:
        meta["stream_verification_message"] = message
    if stream_verification_status == "verified":
        meta["playback_status"] = "verified"
    elif stream_verification_status == "uploaded_not_playing":
        meta["playback_status"] = "uploaded_not_playing"

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET stream_verification_status = ?,
            error_message = COALESCE(?, error_message),
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            stream_verification_status,
            error_message,
            json.dumps(meta, ensure_ascii=False),
            capsule_id,
        ),
    )
    conn.commit()
    conn.close()
    db.add_activity_log(
        "stream_verify",
        f"Capsule {capsule_id} stream_verification_status={stream_verification_status}",
    )
    return enrich_capsule_for_api(get_capsule_by_id(capsule_id) or {})


def send_capsule_to_azuracast(capsule_id: int) -> dict[str, Any]:
    """M4-A3 orchestrator: gate → upload → capsule DB update."""
    from services.broadcast.azuracast_client import (
        check_azuracast_write_config,
        send_capsule_to_azuracast_api,
    )

    gate = validate_capsule_for_azuracast_push(capsule_id)
    if not gate.get("allowed"):
        mark_azuracast_blocked(capsule_id, gate.get("message"))
        return {
            "allowed": False,
            "blocked": True,
            "success": False,
            "capsule_id": capsule_id,
            "mode": "blocked",
            "azuracast_status": "blocked",
            "message": gate.get("message"),
            "error_message": gate.get("message"),
            "next_step": "fix capsule approval/audio before AzuraCast push",
        }

    capsule = gate["capsule"]
    update_capsule_azuracast_result(capsule_id, azuracast_status="uploading", mode="real_api")

    write_cfg = check_azuracast_write_config()
    if write_cfg.get("mode") == "blocked":
        missing = ", ".join(write_cfg.get("missing") or [])
        msg = f"AzuraCast blocked: missing config ({missing})"
        update_capsule_azuracast_result(
            capsule_id,
            azuracast_status="blocked",
            mode="blocked",
            error_message=msg,
        )
        return {
            "allowed": False,
            "blocked": True,
            "success": False,
            "capsule_id": capsule_id,
            "mode": "blocked",
            "azuracast_status": "blocked",
            "message": msg,
            "error_message": msg,
            "next_step": "configure AZURACAST_API_KEY and playlist/folder",
        }

    result = send_capsule_to_azuracast_api(
        capsule_id,
        capsule.get("audio_file_path"),
        title=capsule.get("title"),
    )

    if not result.get("success"):
        update_capsule_azuracast_result(
            capsule_id,
            azuracast_status=result.get("azuracast_status", "failed"),
            mode=result.get("mode", "failed"),
            media_id=result.get("media_id"),
            playlist_id=result.get("playlist_id"),
            truth_level="local_only",
            error_message=result.get("error_message") or result.get("message"),
            metadata_patch={"upload_summary": result.get("upload_summary")},
        )
        return {
            "allowed": False,
            "blocked": result.get("mode") == "blocked",
            "success": False,
            "capsule_id": capsule_id,
            "mode": result.get("mode", "failed"),
            "azuracast_status": result.get("azuracast_status", "failed"),
            "message": result.get("message"),
            "error_message": result.get("error_message"),
            "next_step": "fix AzuraCast config or retry",
        }

    updated = update_capsule_azuracast_result(
        capsule_id,
        azuracast_status=result.get("azuracast_status", "uploaded"),
        mode=result.get("mode", "real_api"),
        media_id=result.get("media_id"),
        playlist_id=result.get("playlist_id"),
        truth_level=result.get("truth_level", "real"),
        error_message=None,
        metadata_patch={"upload_summary": result.get("upload_summary")},
    )

    return {
        "allowed": True,
        "blocked": False,
        "success": True,
        "capsule_id": capsule_id,
        "mode": result.get("mode"),
        "azuracast_status": result.get("azuracast_status"),
        "media_id": result.get("media_id"),
        "playlist_id": result.get("playlist_id"),
        "message": result.get("message"),
        "error_message": None,
        "truth_level": result.get("truth_level"),
        "stream_verification_status": "unknown",
        "next_step": "stream verification pending M4-A4",
        "capsule": updated,
    }


def enrich_capsule_for_api(capsule: dict) -> dict:
    """Add audio_url and playable flags for Command Center (no secrets)."""
    from services.broadcast.azuracast_client import check_azuracast_write_config

    path = capsule.get("audio_file_path") or capsule.get("audio_path")
    # Advisory Command Center flag: existence + truth level only. The hard
    # playability check (_is_playable_audio_file) is enforced at real push time
    # by validate_capsule_for_azuracast_push, so keep this UI flag lenient and
    # consistent with the documented enrich contract.
    if path and os.path.exists(path):
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
        capsule["audio_url"] = f"/playout/voice_assets/{os.path.basename(path)}?v={mtime}"
        capsule["audio_playable"] = capsule.get("audio_truth_level") in ("real", "simulated")
    else:
        capsule["audio_url"] = None
        capsule["audio_playable"] = False

    meta = capsule.get("metadata") or {}
    is_real_audio = capsule.get("audio_truth_level") == "real"
    
    from services.safety.kernel import is_broadcast_ready
    db_broadcast_ready = bool(capsule.get("broadcast_ready"))  # raw DB value (0 or 1)
    az_status = capsule.get("azuracast_status") or "blocked"

    # Simulated audio must never be production_asset or broadcast_ready
    if capsule.get("audio_truth_level") == "simulated":
        capsule["production_asset"] = False
        capsule["broadcast_ready"] = False
    else:
        capsule["production_asset"] = is_real_audio and bool(meta.get("production_asset", True))
        # broadcast_ready requires BOTH real audio AND DB=1 AND AzuraCast in allowed ready statuses
        capsule["broadcast_ready"] = is_broadcast_ready(
            capsule.get("audio_truth_level"),
            db_broadcast_ready,
            az_status
        )

    az_cfg = check_azuracast_write_config()
    capsule["azuracast_config_ready"] = az_cfg.get("ready_for_real_push", False)

    # Script approval lives on approval_status. After real TTS, canonical status
    # becomes audio_ready_preview — that must still be push-ready for chat.
    script_approved = capsule.get("approval_status") == "approved"
    push_stage_ok = (capsule.get("status") or "") in ("approved", "audio_ready_preview")

    capsule["azuracast_push_allowed"] = (
        script_approved
        and push_stage_ok
        and is_real_audio
        and capsule.get("audio_playable")
        and capsule["azuracast_config_ready"]
    )

    if capsule.get("audio_truth_level") == "simulated":
        capsule["azuracast_push_block_reason"] = "Simulated audio broadcast-ready nahi hai"
    elif not script_approved:
        capsule["azuracast_push_block_reason"] = "Owner approval pending"
    elif not push_stage_ok:
        capsule["azuracast_push_block_reason"] = (
            f"Capsule stage '{capsule.get('status')}' push ke liye ready nahi"
        )
    elif not capsule.get("audio_playable") or not is_real_audio:
        capsule["azuracast_push_block_reason"] = "Playable real audio missing"
    elif not capsule["azuracast_config_ready"]:
        missing = ", ".join(az_cfg.get("missing_config") or az_cfg.get("missing") or [])
        capsule["azuracast_push_block_reason"] = (
            f"AzuraCast write config missing ({missing})" if missing else "AzuraCast write config missing"
        )
    else:
        capsule["azuracast_push_block_reason"] = None

    az = capsule.get("azuracast_status") or "blocked"
    sv = capsule.get("stream_verification_status") or "unknown"
    sv_msg = (meta.get("stream_verification_message") or "")
    if sv == "verified":
        capsule["stream_verification_note"] = sv_msg or "Verified: ye capsule abhi stream par chal raha hai"
    elif sv == "uploaded_not_playing":
        capsule["stream_verification_note"] = (
            sv_msg or "Uploaded hai, abhi rotation ka wait kar raha hai"
        )
    elif sv == "failed":
        capsule["stream_verification_note"] = sv_msg or capsule.get("error_message") or "Stream verification failed"
    elif az in ("uploaded", "scheduled"):
        capsule["stream_verification_note"] = "Stream verification pending — Verify Stream dabayein"
    elif is_real_audio and capsule["azuracast_config_ready"]:
        capsule["stream_verification_note"] = (
            "Stream verification M4-A4 tabhi chalega jab real AzuraCast push success hoga."
        )
    last_np = (meta.get("stream_verification_summary") or {}).get("now_playing_snapshot")
    if last_np and sv != "unknown":
        capsule["last_now_playing_snapshot"] = last_np
    capsule["playback_status"] = meta.get("playback_status") or (
        "uploaded_not_playing" if az in ("uploaded", "scheduled") and sv == "uploaded_not_playing" else None
    )
    return capsule


def mark_azuracast_blocked(capsule_id: int, error_message: str | None = None) -> dict:
    msg = error_message or AZURACAST_BLOCKED_MESSAGE
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE broadcast_capsules
        SET azuracast_status = 'blocked', error_message = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (msg, capsule_id),
    )
    conn.commit()
    conn.close()
    capsule = get_capsule_by_id(capsule_id)
    return capsule or {"id": capsule_id, "azuracast_status": "blocked", "error_message": msg}


def block_azuracast_if_not_ready(capsule_id: int) -> dict[str, Any]:
    """Read-only gate check (legacy endpoint) — uses M4-A3 validation."""
    gate = validate_capsule_for_azuracast_push(capsule_id)
    if not gate.get("allowed"):
        mark_azuracast_blocked(capsule_id, gate.get("message"))
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "azuracast_status": "blocked",
            "message": gate.get("message"),
            "truth_level": "local_only",
        }

    from services.broadcast.azuracast_client import check_azuracast_write_config

    cfg = check_azuracast_write_config()
    if cfg.get("mode") == "blocked":
        missing = ", ".join(cfg.get("missing") or [])
        msg = f"AzuraCast blocked: missing config ({missing})"
        mark_azuracast_blocked(capsule_id, msg)
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "azuracast_status": "blocked",
            "message": msg,
            "truth_level": "local_only",
        }

    return {
        "success": True,
        "blocked": False,
        "capsule_id": capsule_id,
        "message": "Capsule and config gates passed. Use send-azuracast to push.",
        "config_mode": cfg.get("mode"),
    }


def ensure_capsule_for_legacy_approval(
    approval_id: int,
    script_text: str,
    asset_type: str,
) -> dict:
    if asset_type not in BROADCAST_ASSET_TYPES and asset_type != "show_script":
        capsule_type = "unknown"
    elif asset_type == "audio_ad":
        capsule_type = "ad_script"
    elif asset_type == "show_plan":
        capsule_type = "daily_show_plan"
    else:
        capsule_type = "unknown"

    return create_capsule_from_script(
        approval_queue_id=approval_id,
        script_text=script_text,
        capsule_type=capsule_type,
        source="legacy_script_output",
        metadata={"asset_type": asset_type},
    )


__all__ = [
    "AZURACAST_BLOCKED_MESSAGE",
    "AUDIO_APPROVAL_BLOCKED_MESSAGE",
    "queue_script_and_create_capsule",
    "create_capsule_from_script",
    "get_capsule_by_id",
    "get_capsule_by_approval_queue_id",
    "list_recent_capsules",
    "update_capsule_approval_status",
    "update_capsule_audio_status",
    "link_audio_asset_to_capsule",
    "validate_capsule_for_audio_generation",
    "validate_capsule_for_azuracast_push",
    "update_capsule_azuracast_result",
    "update_capsule_stream_verification",
    "update_capsule_playback_result",
    "send_capsule_to_azuracast",
    "enrich_capsule_for_api",
    "mark_azuracast_blocked",
    "block_azuracast_if_not_ready",
    "ensure_capsule_for_legacy_approval",
    "append_capsule_footer",
]

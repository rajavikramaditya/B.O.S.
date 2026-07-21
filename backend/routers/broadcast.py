"""Broadcast + capsule HTTP domain (M4-A1..A4.5).

Single responsibility: capsule lifecycle (create/list/approve/reject),
audio generation, AzuraCast push and stream/playback verification. Depends
only on domain services — no shared app globals — so it stays replaceable.
"""
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _record_broadcast(action: str, capsule_id: int | None, result: dict[str, Any] | None, started: float) -> None:
    try:
        from services.cockpit.recorder import record_broadcast_turn

        record_broadcast_turn(
            action=action,
            capsule_id=capsule_id,
            result=result if isinstance(result, dict) else {"reply": str(result)},
            latency_ms=round((time.monotonic() - started) * 1000),
        )
    except Exception:
        logger.debug("broadcast recorder write skipped", exc_info=True)

class CreateCapsuleRequest(BaseModel):
    script_text: str
    capsule_type: str = "unknown"
    title: str | None = None
    topic: str | None = None
    language: str | None = None
    tone: str | None = None
    created_by: str | None = None


class RejectCapsuleRequest(BaseModel):
    reason: str = "No reason provided"
    rejected_by: str = "owner"


@router.post("/api/neena/capsules")
def post_create_capsule(data: CreateCapsuleRequest):
    from services.broadcast.capsule_service import create_capsule_from_script
    from services.broadcast.approval_queue import queue_asset_for_review

    started = time.monotonic()
    legacy_asset_type = "show_script"
    if data.capsule_type == "ad_script":
        legacy_asset_type = "audio_ad"
    elif data.capsule_type == "daily_show_plan":
        legacy_asset_type = "show_plan"

    approval_id = queue_asset_for_review(legacy_asset_type, data.script_text)

    capsule = create_capsule_from_script(
        approval_queue_id=approval_id,
        script_text=data.script_text,
        capsule_type=data.capsule_type,
        title=data.title,
        source="api",
        topic=data.topic,
        language=data.language,
        tone=data.tone,
        created_by=data.created_by,
        status="pending_approval",
    )
    out = {"status": "success", "capsule": capsule, "ok": True}
    cid = capsule.get("id") if isinstance(capsule, dict) else None
    _record_broadcast("create", cid, out, started)
    return out


@router.get("/api/neena/capsules")
def get_list_capsules(limit: int = 20):
    from services.broadcast.capsule_service import list_recent_capsules
    capsules = list_recent_capsules(limit=min(limit, 50))
    return {"status": "success", "capsules": capsules, "count": len(capsules)}


@router.get("/api/neena/capsules/latest")
def get_latest_neena_capsule():
    from services.broadcast.capsule_service import get_latest_capsule, enrich_capsule_for_api
    cap = get_latest_capsule()
    if not cap:
        raise HTTPException(status_code=404, detail="No capsules found.")
    return {"status": "success", "capsule": enrich_capsule_for_api(cap)}


@router.get("/api/neena/capsules/{capsule_id}")
def get_neena_capsule_by_id(capsule_id: int):
    from services.broadcast.capsule_service import get_capsule_by_id, enrich_capsule_for_api
    cap = get_capsule_by_id(capsule_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capsule #{capsule_id} not found.")
    return {"status": "success", "capsule": enrich_capsule_for_api(cap)}


@router.get("/api/neena/capsules/{capsule_id}/audio")
def get_capsule_audio_file(capsule_id: int):
    from services.broadcast.capsule_service import get_capsule_by_id
    from services.voice.gen_service import VOICE_ASSETS_DIR

    cap = get_capsule_by_id(capsule_id)
    if not cap:
        raise HTTPException(status_code=404, detail="Capsule not found.")

    filepath = cap.get("audio_file_path")
    if not filepath:
        raise HTTPException(status_code=404, detail="Audio file path is empty for this capsule.")

    # Safety Check: Directory Traversal Protection
    try:
        abs_assets = Path(VOICE_ASSETS_DIR).resolve()
        abs_file = Path(filepath).resolve()
        abs_file.relative_to(abs_assets)
    except ValueError:
        # Do not leak absolute path in logs or errors
        logger.warning(f"Path traversal safety block triggered for capsule #{capsule_id}")
        raise HTTPException(status_code=403, detail="Access denied: invalid file location.")

    if not abs_file.exists():
        raise HTTPException(status_code=404, detail="Audio file does not exist on disk.")

    media_type = "audio/wav" if filepath.endswith(".wav") else "audio/mpeg"
    filename = os.path.basename(filepath)
    return FileResponse(str(abs_file), media_type=media_type, filename=filename)


@router.post("/api/neena/capsules/{capsule_id}/approve")
def post_approve_neena_capsule(capsule_id: int, approved_by: str = "owner"):
    from services.broadcast.capsule_service import get_capsule_by_id, approve_capsule
    from services.broadcast.approval_queue import process_approval_action

    started = time.monotonic()
    cap = get_capsule_by_id(capsule_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capsule #{capsule_id} not found.")

    aid = cap.get("approval_queue_id")
    if aid:
        try:
            process_approval_action(int(aid), "approve")
        except Exception:
            pass

    updated = approve_capsule(capsule_id, approved_by=approved_by)
    out = {"status": "success", "capsule": updated, "ok": True}
    _record_broadcast("approve", capsule_id, out, started)
    return out


@router.post("/api/neena/capsules/{capsule_id}/reject")
def post_reject_neena_capsule(capsule_id: int, data: RejectCapsuleRequest):
    from services.broadcast.capsule_service import get_capsule_by_id, reject_capsule
    from services.broadcast.approval_queue import process_approval_action

    started = time.monotonic()
    cap = get_capsule_by_id(capsule_id)
    if not cap:
        raise HTTPException(status_code=404, detail=f"Capsule #{capsule_id} not found.")

    aid = cap.get("approval_queue_id")
    if aid:
        try:
            process_approval_action(int(aid), "reject")
        except Exception:
            pass

    updated = reject_capsule(capsule_id, rejected_by=data.rejected_by, reason=data.reason)
    out = {"status": "success", "capsule": updated, "ok": True}
    _record_broadcast("reject", capsule_id, out, started)
    return out


@router.post("/api/neena/capsules/{capsule_id}/prepare-audio")
def post_prepare_capsule_audio(capsule_id: int):
    from services.voice.gen_service import generate_capsule_audio

    started = time.monotonic()
    result = generate_capsule_audio(capsule_id, regenerate=True)
    if result.get("blocked"):
        _record_broadcast("prepare_audio", capsule_id, {**result, "ok": False, "blocked": True}, started)
        raise HTTPException(status_code=400, detail=result.get("message"))
    if not result.get("success"):
        _record_broadcast("prepare_audio", capsule_id, {**result, "ok": False}, started)
        raise HTTPException(status_code=500, detail=result.get("message", "Audio generation failed."))
    _record_broadcast("prepare_audio", capsule_id, {**result, "ok": True}, started)
    return result


@router.get("/api/neena/capsules/status")
def get_neena_capsules_status():
    from services.broadcast.capsule_service import get_capsules_status_summary
    summary = get_capsules_status_summary()
    return {"status": "success", "summary": summary}


@router.get("/api/broadcast/capsules")
def list_broadcast_capsules(limit: int = 20):
    from services.broadcast.capsule_service import list_recent_capsules
    capsules = list_recent_capsules(limit=min(limit, 50))
    return {"status": "success", "capsules": capsules, "count": len(capsules)}


@router.get("/api/broadcast/capsules/{capsule_id}")
def get_broadcast_capsule(capsule_id: int):
    from services.broadcast.capsule_service import enrich_capsule_for_api, get_capsule_by_id
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail=f"Broadcast capsule {capsule_id} not found.")
    return {"status": "success", "capsule": enrich_capsule_for_api(capsule)}


@router.post("/api/broadcast/capsules/{capsule_id}/generate-audio")
def post_generate_capsule_audio(capsule_id: int):
    from services.voice.gen_service import generate_capsule_audio
    started = time.monotonic()
    result = generate_capsule_audio(capsule_id, regenerate=False)
    if result.get("blocked"):
        _record_broadcast("generate_audio", capsule_id, {**result, "ok": False, "blocked": True}, started)
        raise HTTPException(status_code=400, detail=result.get("message"))
    if not result.get("success"):
        _record_broadcast("generate_audio", capsule_id, {**result, "ok": False}, started)
        raise HTTPException(status_code=500, detail=result.get("message", "Audio generation failed."))
    _record_broadcast("generate_audio", capsule_id, {**result, "ok": True}, started)
    return result


@router.post("/api/broadcast/capsules/{capsule_id}/regenerate-audio")
def post_regenerate_capsule_audio(capsule_id: int):
    from services.voice.gen_service import generate_capsule_audio
    started = time.monotonic()
    result = generate_capsule_audio(capsule_id, regenerate=True)
    if result.get("blocked"):
        _record_broadcast("regenerate_audio", capsule_id, {**result, "ok": False, "blocked": True}, started)
        raise HTTPException(status_code=400, detail=result.get("message"))
    if not result.get("success"):
        _record_broadcast("regenerate_audio", capsule_id, {**result, "ok": False}, started)
        raise HTTPException(status_code=500, detail=result.get("message", "Audio regeneration failed."))
    _record_broadcast("regenerate_audio", capsule_id, {**result, "ok": True}, started)
    return result


@router.post("/api/broadcast/capsules/{capsule_id}/block-azuracast-check")
def block_broadcast_capsule_azuracast(capsule_id: int):
    from services.broadcast.capsule_service import block_azuracast_if_not_ready
    started = time.monotonic()
    result = block_azuracast_if_not_ready(capsule_id)
    _record_broadcast("block_azuracast_check", capsule_id, result if isinstance(result, dict) else {"reply": str(result)}, started)
    return result


@router.post("/api/broadcast/capsules/{capsule_id}/send-azuracast")
def send_broadcast_capsule_azuracast(capsule_id: int):
    """M4-A3 — real AzuraCast push for approved capsules with real playable audio."""
    from services.broadcast.capsule_service import send_capsule_to_azuracast

    started = time.monotonic()
    result = send_capsule_to_azuracast(capsule_id)
    _record_broadcast(
        "send_azuracast",
        capsule_id,
        result if isinstance(result, dict) else {"reply": str(result)},
        started,
    )
    return result


@router.get("/api/broadcast/azuracast/write-config")
def get_azuracast_write_config():
    """Read-only AzuraCast write config presence (no secrets)."""
    from services.broadcast.azuracast_client import check_azuracast_write_config
    return {"status": "success", "config": check_azuracast_write_config()}


@router.get("/api/broadcast/audio/readiness")
def get_broadcast_audio_readiness():
    """TTS + AzuraCast combined readiness (no secrets)."""
    from services.voice.gen_service import get_broadcast_audio_readiness
    return {"status": "success", "readiness": get_broadcast_audio_readiness()}


@router.get("/api/broadcast/audio/provider-readiness")
def get_audio_provider_readiness():
    """TTS provider readiness only (no secrets)."""
    from services.voice.gen_service import check_audio_provider_readiness
    return {"status": "success", "providers": check_audio_provider_readiness()}


@router.post("/api/broadcast/capsules/{capsule_id}/verify-stream")
def post_verify_capsule_stream(capsule_id: int, watch_seconds: int = 0):
    """M4-A4 — verify uploaded capsule against stream / now-playing."""
    from services.broadcast.stream_verification import verify_capsule_stream_status

    started = time.monotonic()
    result = verify_capsule_stream_status(capsule_id, watch_seconds=watch_seconds)
    if result.get("blocked") and not result.get("success"):
        _record_broadcast("verify_stream", capsule_id, {**result, "ok": False, "blocked": True}, started)
        raise HTTPException(status_code=400, detail=result.get("message"))
    _record_broadcast("verify_stream", capsule_id, {**result, "ok": True}, started)
    return result


@router.get("/api/broadcast/capsules/{capsule_id}/stream-verification")
def get_capsule_stream_verification(capsule_id: int):
    """Read last stream verification state for a capsule."""
    from services.broadcast.stream_verification import get_capsule_stream_verification

    result = get_capsule_stream_verification(capsule_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
    return result


@router.post("/api/broadcast/capsules/{capsule_id}/ensure-playback")
def post_ensure_capsule_playback(capsule_id: int, mode: str = "auto", watch_seconds: int = 0):
    """M4-A4.5 — queue/playlist playback control for uploaded capsules."""
    from services.broadcast.playback_control import ensure_capsule_playback

    started = time.monotonic()
    result = ensure_capsule_playback(capsule_id, mode=mode, watch_seconds=watch_seconds)
    if result.get("blocked"):
        _record_broadcast("ensure_playback", capsule_id, {**result, "ok": False, "blocked": True}, started)
        raise HTTPException(status_code=400, detail=result.get("message"))
    _record_broadcast("ensure_playback", capsule_id, {**result, "ok": True}, started)
    return result

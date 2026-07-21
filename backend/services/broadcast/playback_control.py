"""M4-A4.5 — AzuraCast playback / queue control for uploaded capsules."""
from __future__ import annotations

import logging
import time
from typing import Any

from services.broadcast.azuracast_client import (
    append_media_to_playlist,
    get_media_file_info,
    get_playlist_info,
    get_station_playback_snapshot,
    queue_media_files_batch,
)
from services.broadcast.capsule_service import (
    enrich_capsule_for_api,
    get_capsule_by_id,
    update_capsule_playback_result,
)
from services.broadcast.stream_verification import verify_capsule_stream_status

logger = logging.getLogger(__name__)

VALID_MODES = frozenset({"auto", "ensure_playlist", "queue_now"})


def _capsule_media_path(capsule: dict, media_info: dict | None = None) -> str | None:
    meta = capsule.get("metadata") or {}
    upload = meta.get("upload_summary") or {}
    if upload.get("path"):
        return str(upload["path"])
    if media_info and media_info.get("path"):
        return str(media_info["path"])
    audio = capsule.get("audio_file_path") or ""
    if audio:
        folder = upload.get("target_folder") or "neena-capsules"
        import os
        return f"{folder.strip('/')}/{os.path.basename(audio)}"
    return None


def _gate_capsule(capsule_id: int) -> dict[str, Any]:
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return {"blocked": True, "message": "Capsule not found."}
    if capsule.get("audio_truth_level") == "simulated":
        return {"blocked": True, "message": "Simulated audio production playback ke liye blocked hai."}
    az = capsule.get("azuracast_status") or "not_sent"
    if az not in ("uploaded", "scheduled"):
        return {
            "blocked": True,
            "message": f"Playback blocked: azuracast_status '{az}' — pehle uploaded/scheduled hona chahiye.",
        }
    media_id = capsule.get("azuracast_media_id") or (capsule.get("metadata") or {}).get("azuracast_media_id")
    if not media_id:
        return {"blocked": True, "message": "Playback blocked: azuracast_media_id missing."}
    return {"blocked": False, "capsule": capsule, "media_id": str(media_id)}


def ensure_capsule_playback(
    capsule_id: int,
    *,
    mode: str = "auto",
    watch_seconds: int = 0,
    playlist_id: str | None = None,
) -> dict[str, Any]:
    """
    Ensure uploaded capsule enters AzuraCast playback path.
    mode: auto | ensure_playlist | queue_now
    playlist_id: optional Azura playlist target (else env default).
    """
    mode = (mode or "auto").strip().lower()
    if mode not in VALID_MODES:
        mode = "auto"

    gate = _gate_capsule(capsule_id)
    if gate.get("blocked"):
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "playback_status": "failed",
            "message": gate.get("message"),
        }

    capsule = gate["capsule"]
    media_id = gate["media_id"]
    actions: list[str] = []
    safe_details: dict[str, Any] = {"mode": mode, "media_id": media_id}
    if playlist_id:
        safe_details["requested_playlist_id"] = str(playlist_id)

    media_info = get_media_file_info(media_id)
    safe_details["media_info"] = {
        k: media_info.get(k)
        for k in ("found", "path", "title", "playlists", "error")
        if k in media_info
    }
    if not media_info.get("found"):
        return {
            "success": False,
            "capsule_id": capsule_id,
            "media_id": media_id,
            "playback_status": "failed",
            "action_taken": "none",
            "message": media_info.get("error") or "Media AzuraCast me nahi mila.",
            "safe_details": safe_details,
        }

    media_path = _capsule_media_path(capsule, media_info)
    safe_details["media_path"] = media_path
    playback_status = "uploaded_not_playing"
    playlist_assigned = bool(media_info.get("playlists"))

    snapshot = get_station_playback_snapshot()
    safe_details["station_snapshot"] = snapshot

    if mode in ("auto", "ensure_playlist"):
        playlists = media_info.get("playlists") or []
        target_pid = str(playlist_id).strip() if playlist_id else ""
        already_on_target = False
        if target_pid and playlists:
            already_on_target = any(
                str(p.get("id")) == target_pid for p in playlists if isinstance(p, dict)
            )
        if playlists and (not target_pid or already_on_target):
            playback_status = "playlist_assigned"
            actions.append("media_already_in_playlist")
            safe_details["playlists"] = [
                {"id": p.get("id"), "name": p.get("name"), "folder": p.get("folder")}
                for p in playlists[:5]
                if isinstance(p, dict)
            ]
        else:
            from services.broadcast.azuracast_client import _get_playlist_id

            pid = target_pid or _get_playlist_id()
            if pid:
                append = append_media_to_playlist(media_id, playlist_id=pid, file_path=media_path)
                safe_details["playlist_append"] = append
                safe_details["playlist_id"] = str(pid)
                if append.get("success"):
                    playback_status = "playlist_assigned"
                    actions.append("playlist_append")
                else:
                    playback_status = "queue_failed"
                    actions.append("playlist_append_failed")
            else:
                actions.append("no_playlist_id_configured")

    if mode in ("auto", "queue_now") and media_path:
        batch_mode = "immediate" if mode == "queue_now" else "queue"
        batch = queue_media_files_batch([media_path], do=batch_mode)
        safe_details["batch_queue"] = batch
        if batch.get("success"):
            playback_status = "queued" if batch_mode == "queue" else "queued"
            actions.append(f"batch_{batch_mode}")
            if batch_mode == "immediate":
                actions.append("play_immediate_requested")
        elif batch.get("capability_missing"):
            if playback_status == "uploaded_not_playing":
                playback_status = "autodj_pending"
            actions.append("batch_capability_missing")
        else:
            playback_status = "queue_failed"
            actions.append("batch_failed")

    if playback_status in ("playlist_assigned", "queued") and not snapshot.get("requests_enabled"):
        playback_status = "autodj_pending" if playback_status == "playlist_assigned" else playback_status

    message = _playback_message(playback_status, media_path, actions)

    update_capsule_playback_result(
        capsule_id,
        playback_status=playback_status,
        action_taken=",".join(actions) or "none",
        metadata_patch={
            "playback_control": {
                "mode": mode,
                "actions": actions,
                "media_path": media_path,
                "media_playlists": safe_details.get("playlists"),
            }
        },
    )

    verify_result = None
    watch_seconds = max(0, min(int(watch_seconds or 0), 180))
    if watch_seconds > 0 or mode == "queue_now":
        verify_watch = watch_seconds or 60
        verify_result = verify_capsule_stream_status(capsule_id, watch_seconds=verify_watch)
        if verify_result.get("verification_status") == "verified":
            playback_status = "verified"
            message = verify_result.get("message") or message

    result = {
        "success": playback_status not in ("failed", "queue_failed"),
        "capsule_id": capsule_id,
        "media_id": media_id,
        "media_path": media_path,
        "action_taken": ",".join(actions) or "none",
        "playback_status": playback_status,
        "stream_verification_status": (
            verify_result.get("stream_verification_status")
            if verify_result
            else capsule.get("stream_verification_status", "unknown")
        ),
        "now_playing_match": verify_result.get("now_playing_match") if verify_result else False,
        "message": message,
        "safe_details": safe_details,
        "next_step": _next_step(playback_status, verify_result),
    }
    if verify_result:
        result["verification"] = {
            "verification_status": verify_result.get("verification_status"),
            "now_playing_snapshot": verify_result.get("now_playing_snapshot"),
            "watch_polls": verify_result.get("watch_polls", 0),
        }
    result["capsule"] = enrich_capsule_for_api(get_capsule_by_id(capsule_id) or capsule)
    return result


def _playback_message(status: str, media_path: str | None, actions: list[str]) -> str:
    if status == "verified":
        return "Verified: ye capsule abhi stream par chal raha hai."
    if status == "queued":
        return f"Media queue me add ho gayi ({media_path or 'path'}). AutoDJ rotation ka wait."
    if status == "playlist_assigned":
        return (
            "Media playlist me assigned hai, lekin abhi stream par nahi chal rahi. "
            "Queue action try kiya ya AutoDJ rotation ka wait."
        )
    if status == "autodj_pending":
        return "Media uploaded hai, lekin playlist/AutoDJ ne abhi pick nahi kiya."
    if status == "queue_failed":
        return "Queue/playlist action fail — API error ya capability missing."
    if status == "uploaded_not_playing":
        return "Uploaded hai, playback path abhi confirm nahi hua."
    return "Playback status unknown."


def _next_step(playback_status: str, verify_result: dict | None) -> str:
    if playback_status == "verified" or (verify_result and verify_result.get("verification_status") == "verified"):
        return "M4-A5 launch rehearsal / Command Center polish"
    if playback_status in ("queued", "playlist_assigned", "autodj_pending", "uploaded_not_playing"):
        return "Watch 60s verify-stream ya AZURACAST_PLAYLIST_ID + AutoDJ settings check (M4-A4.5)"
    return "Fix AzuraCast playback config or retry ensure-playback"


__all__ = ["ensure_capsule_playback"]

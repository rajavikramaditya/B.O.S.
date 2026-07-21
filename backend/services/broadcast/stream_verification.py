"""M4-A4 — truthful stream verification for uploaded broadcast capsules."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

from services.broadcast.azuracast_client import (
    _api_headers,
    _api_verify_ssl,
    _get_api_key,
    _get_base_url,
    _get_station_id,
    _get_station_shortcode,
    _get_stream_url,
    _is_configured,
)
from services.broadcast.capsule_service import (
    enrich_capsule_for_api,
    get_capsule_by_id,
    update_capsule_stream_verification,
)

logger = logging.getLogger(__name__)

WATCH_POLL_SECONDS = 12
WATCH_MAX_SECONDS = 180


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def check_stream_url() -> dict[str, Any]:
    """HEAD/GET stream mount — reachable if HTTP 200/206."""
    stream_url = _get_stream_url()
    if not _is_configured(stream_url):
        return {"stream_reachable": False, "stream_url_configured": False, "error": "stream_url_missing"}
    try:
        res = requests.get(stream_url, stream=True, timeout=8.0, verify=_api_verify_ssl())
        ok = res.status_code in (200, 206)
        res.close()
        return {"stream_reachable": ok, "stream_url_configured": True, "http_status": res.status_code}
    except Exception as exc:
        logger.warning("Stream URL check failed: %s", exc)
        return {"stream_reachable": False, "stream_url_configured": True, "error": exc.__class__.__name__}


def _azuracast_api_reachable() -> bool:
    base = _get_base_url()
    if not _is_configured(base):
        return False
    shortcode = _get_station_shortcode()
    station_id = _get_station_id()
    slug = shortcode if shortcode else station_id
    url = f"{base.rstrip('/')}/api/nowplaying/{slug}"
    try:
        res = requests.get(url, timeout=8.0, verify=_api_verify_ssl())
        return res.status_code == 200
    except Exception:
        return False


def get_now_playing_snapshot() -> dict[str, Any]:
    """Fetch AzuraCast now-playing JSON (public or station slug)."""
    base = _get_base_url()
    if not _is_configured(base):
        return {"checked": False, "error": "azuracast_base_missing"}

    shortcode = _get_station_shortcode()
    station_id = _get_station_id()
    slug = shortcode if shortcode else station_id
    url = f"{base.rstrip('/')}/api/nowplaying/{slug}"
    try:
        res = requests.get(url, timeout=8.0, verify=_api_verify_ssl())
        if res.status_code != 200:
            return {"checked": True, "error": f"nowplaying_http_{res.status_code}"}
        data = res.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        np = data.get("now_playing") or {}
        if isinstance(np, list):
            np = np[0] if np else {}
        song = np.get("song") or {}
        if isinstance(song, list):
            song = song[0] if song else {}
        station = data.get("station") or {}
        if isinstance(station, list):
            station = station[0] if station else {}
        listeners_block = data.get("listeners") or {}
        if isinstance(listeners_block, list):
            listeners_block = listeners_block[0] if listeners_block else {}
        listeners = listeners_block.get("total", 0) if isinstance(listeners_block, dict) else 0
        custom = song.get("custom_fields") or {}
        if not isinstance(custom, dict):
            custom = {}
        return {
            "checked": True,
            "station_online": station.get("is_enabled", True) if isinstance(station, dict) else True,
            "is_live": data.get("is_live", False),
            "listeners": listeners,
            "elapsed": np.get("elapsed"),
            "remaining": np.get("remaining"),
            "duration": np.get("duration"),
            "title": song.get("title") or "",
            "artist": song.get("artist") or "",
            "text": song.get("text") or "",
            "song_id": song.get("id"),
            "song_unique_id": song.get("unique_id") or song.get("id"),
            "path": song.get("path") or custom.get("path") or "",
            "raw_song_keys": list(song.keys())[:12] if isinstance(song, dict) else [],
        }
    except Exception as exc:
        logger.warning("Now playing snapshot failed: %s", exc)
        return {"checked": False, "error": exc.__class__.__name__}


def verify_uploaded_media_if_supported(capsule: dict) -> dict[str, Any]:
    """Check media still exists in AzuraCast via admin API when key + media_id present."""
    media_id = capsule.get("azuracast_media_id") or (capsule.get("metadata") or {}).get("azuracast_media_id")
    base = _get_base_url()
    api_key = _get_api_key()
    station_id = _get_station_id()

    if not media_id:
        return {"media_uploaded_verified": "unknown", "reason": "no_media_id_on_capsule"}
    if not _is_configured(base) or not _is_configured(api_key):
        return {"media_uploaded_verified": "unknown", "reason": "api_key_or_base_missing"}

    url = f"{base.rstrip('/')}/api/station/{station_id}/file/{media_id}"
    try:
        res = requests.get(url, headers=_api_headers(), timeout=10.0, verify=_api_verify_ssl())
        if res.status_code == 200:
            body = res.json() if res.content else {}
            return {
                "media_uploaded_verified": True,
                "media_path": body.get("path") or body.get("formatted_path"),
                "media_name": body.get("name") or body.get("title"),
            }
        if res.status_code == 404:
            return {"media_uploaded_verified": False, "reason": "media_not_found_in_azuracast"}
        return {"media_uploaded_verified": "unknown", "reason": f"media_api_http_{res.status_code}"}
    except Exception as exc:
        return {"media_uploaded_verified": "unknown", "reason": exc.__class__.__name__}


def match_capsule_against_now_playing(
    capsule: dict,
    now_playing: dict,
    *,
    media_check: dict | None = None,
) -> dict[str, Any]:
    """Layered match — only strong matches yield verified confidence."""
    if not now_playing.get("checked"):
        return {
            "now_playing_checked": False,
            "now_playing_match": False,
            "match_confidence": "none",
            "match_reason": "now_playing_unavailable",
        }

    meta = capsule.get("metadata") or {}
    media_id = str(capsule.get("azuracast_media_id") or meta.get("azuracast_media_id") or "")
    audio_path = capsule.get("audio_file_path") or ""
    filename = os.path.basename(audio_path) if audio_path else ""
    upload_path = (meta.get("upload_summary") or {}).get("path") or ""
    media_api_path = (media_check or {}).get("media_path") or ""

    song_id = str(now_playing.get("song_id") or "")
    song_uid = str(now_playing.get("song_unique_id") or "")
    np_path = now_playing.get("path") or ""
    np_title = now_playing.get("title") or ""
    np_artist = now_playing.get("artist") or ""
    np_text = now_playing.get("text") or ""

    candidates_path = [p for p in (upload_path, media_api_path, filename) if p]
    candidates_norm = {_norm(p) for p in candidates_path}
    candidates_norm.add(_norm(filename.replace(".wav", "").replace(".mp3", "")))

    # 1. Media ID
    if media_id and media_id in (song_id, song_uid):
        return {
            "now_playing_checked": True,
            "now_playing_match": True,
            "match_confidence": "high",
            "match_reason": "media_id_match",
        }

    # 2. Path
    if np_path:
        np_norm = _norm(np_path)
        for c in candidates_path:
            if c and (c in np_path or np_path.endswith(c) or _norm(c) in np_norm):
                return {
                    "now_playing_checked": True,
                    "now_playing_match": True,
                    "match_confidence": "high",
                    "match_reason": "path_match",
                }

    # 3. Filename in text/title
    if filename:
        fn_base = filename.rsplit(".", 1)[0]
        hay = f"{np_text} {np_title} {np_artist}".lower()
        hay_norm = _norm(hay)
        if filename.lower() in hay or fn_base.lower() in hay:
            return {
                "now_playing_checked": True,
                "now_playing_match": True,
                "match_confidence": "medium",
                "match_reason": "filename_in_now_playing",
            }
        if _norm(fn_base) and _norm(fn_base) in hay_norm:
            return {
                "now_playing_checked": True,
                "now_playing_match": True,
                "match_confidence": "medium",
                "match_reason": "filename_normalized_match",
            }

    # 4. Title metadata (weak)
    capsule_title = capsule.get("title") or ""
    if capsule_title and len(capsule_title) > 4:
        if _norm(capsule_title) in _norm(np_text) or _norm(capsule_title) in _norm(np_title):
            return {
                "now_playing_checked": True,
                "now_playing_match": False,
                "match_confidence": "weak",
                "match_reason": "title_weak_match_only",
            }

    return {
        "now_playing_checked": True,
        "now_playing_match": False,
        "match_confidence": "none",
        "match_reason": "no_match",
        "now_playing_title": np_title,
        "now_playing_artist": np_artist,
    }


def _build_verification_result(
    capsule: dict,
    *,
    azuracast_reachable: bool,
    stream_info: dict,
    media_check: dict,
    match: dict,
    now_playing: dict,
) -> dict[str, Any]:
    stream_ok = stream_info.get("stream_reachable", False)
    media_ver = media_check.get("media_uploaded_verified")
    np_checked = match.get("now_playing_checked", False)
    np_match = match.get("now_playing_match", False)
    confidence = match.get("match_confidence", "none")

    if not azuracast_reachable:
        status = "failed"
        message = "AzuraCast reachable nahi hai — base URL ya now-playing check fail."
    elif not stream_ok and stream_info.get("stream_url_configured"):
        status = "failed"
        message = "Stream URL reachable nahi hai — Icecast/stream offline lag raha hai."
    elif np_match and confidence in ("high", "medium"):
        status = "verified"
        message = "Verified: ye capsule abhi stream par chal raha hai."
    elif media_ver is True and stream_ok and azuracast_reachable:
        status = "uploaded_not_playing"
        message = (
            "Capsule AzuraCast me uploaded hai, stream online hai, "
            "lekin abhi now-playing me ye capsule nahi chal raha."
        )
    elif stream_ok and np_checked and not np_match:
        status = "stream_online_unknown_match"
        message = "Stream online hai, par is capsule ka exact now-playing match confirm nahi hua."
    elif media_ver is False:
        status = "failed"
        message = "Uploaded media AzuraCast me nahi mila — upload verify fail."
    else:
        status = "unknown"
        message = "Verification incomplete — config ya match data insufficient."

    safe_np = {
        "title": now_playing.get("title"),
        "artist": now_playing.get("artist"),
        "elapsed": now_playing.get("elapsed"),
        "remaining": now_playing.get("remaining"),
        "duration": now_playing.get("duration"),
        "listeners": now_playing.get("listeners"),
        "is_live": now_playing.get("is_live"),
    }

    db_status = status
    if status == "stream_online_unknown_match":
        db_status = "unknown"

    return {
        "capsule_id": capsule.get("id"),
        "azuracast_status": capsule.get("azuracast_status"),
        "verification_status": status,
        "stream_verification_status": db_status,
        "azuracast_reachable": azuracast_reachable,
        "stream_reachable": stream_ok,
        "media_uploaded_verified": media_ver,
        "now_playing_checked": np_checked,
        "now_playing_match": np_match,
        "match_confidence": confidence,
        "match_reason": match.get("match_reason"),
        "now_playing_snapshot": safe_np,
        "message": message,
        "safe_details": {
            "media_check": {k: v for k, v in media_check.items() if k != "raw"},
            "stream_http_status": stream_info.get("http_status"),
            "match_reason": match.get("match_reason"),
        },
        "next_step": (
            "M4-A5 launch rehearsal / Command Center polish"
            if status == "verified"
            else (
                "M4-A4.5 playlist/queue playback control — AutoDJ rotation check"
                if status == "uploaded_not_playing"
                else "Fix stream/AzuraCast config or retry verify"
            )
        ),
    }


def _single_verify_pass(capsule: dict) -> dict[str, Any]:
    az_ok = _azuracast_api_reachable()
    stream_info = check_stream_url()
    now_playing = get_now_playing_snapshot()
    media_check = verify_uploaded_media_if_supported(capsule)
    match = match_capsule_against_now_playing(capsule, now_playing, media_check=media_check)
    return _build_verification_result(
        capsule,
        azuracast_reachable=az_ok,
        stream_info=stream_info,
        media_check=media_check,
        match=match,
        now_playing=now_playing,
    )


def verify_capsule_stream_status(capsule_id: int, *, watch_seconds: int = 0) -> dict[str, Any]:
    """Verify uploaded capsule against stream / now-playing. Optional watch polling."""
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "verification_status": "unknown",
            "message": "Capsule not found.",
        }

    az_status = capsule.get("azuracast_status") or "not_sent"
    if az_status not in ("uploaded", "scheduled"):
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "azuracast_status": az_status,
            "verification_status": "unknown",
            "stream_verification_status": "unknown",
            "message": (
                f"Stream verify blocked: capsule AzuraCast status '{az_status}' — "
                "pehle uploaded/scheduled hona chahiye."
            ),
        }

    # Webhook-first: short event wait + one-shot. No multi-minute poll theatre.
    watch_seconds = max(0, min(int(watch_seconds or 0), WATCH_MAX_SECONDS))
    result = _single_verify_pass(capsule)

    if watch_seconds > 0 and result.get("verification_status") != "verified":
        try:
            from services.broadcast.azura_events import wait_for_webhook_or_oneshot

            fast = wait_for_webhook_or_oneshot(
                capsule_id=capsule_id,
                timeout_seconds=min(float(watch_seconds), 12.0),
            )
            result["azura_fast_path"] = fast.get("path")
            result["webhook_event"] = fast.get("webhook_event")
        except Exception:
            pass
        capsule = get_capsule_by_id(capsule_id) or capsule
        attempt = _single_verify_pass(capsule)
        attempt["watch_polls"] = 0
        attempt["azura_fast_path"] = result.get("azura_fast_path")
        if attempt.get("verification_status") == "verified":
            result = attempt
            result["message"] = (
                "Verified (webhook/oneshot): ye capsule abhi stream par match kar raha hai."
            )
        else:
            result = attempt
            if result.get("verification_status") == "uploaded_not_playing":
                result["message"] = (
                    "Upload/command gayi hai; abhi stream pe match nahi mila. "
                    "Jab Azura webhook/nowplaying reflect karega, phir verify clear hoga — "
                    "60s guess fail nahi."
                )

    summary = {
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verification_status": result.get("verification_status"),
        "now_playing_snapshot": result.get("now_playing_snapshot"),
        "match_reason": result.get("match_reason"),
        "match_confidence": result.get("match_confidence"),
        "watch_polls": result.get("watch_polls", 0),
    }
    updated = update_capsule_stream_verification(
        capsule_id,
        result.get("stream_verification_status", "unknown"),
        message=result.get("message"),
        metadata_patch={"stream_verification_summary": summary},
        error_message=None if result.get("verification_status") != "failed" else result.get("message"),
    )
    result["success"] = result.get("verification_status") not in ("failed",)
    result["capsule"] = updated or enrich_capsule_for_api(capsule)
    return result


def get_capsule_stream_verification(capsule_id: int) -> dict[str, Any]:
    """Read last verification state from capsule + optional live refresh flag false."""
    capsule = get_capsule_by_id(capsule_id)
    if not capsule:
        return {"success": False, "message": "Capsule not found."}
    meta = capsule.get("metadata") or {}
    return {
        "success": True,
        "capsule_id": capsule_id,
        "capsule": enrich_capsule_for_api(capsule),
        "stream_verification_status": capsule.get("stream_verification_status", "unknown"),
        "last_summary": meta.get("stream_verification_summary"),
    }


__all__ = [
    "verify_capsule_stream_status",
    "get_capsule_stream_verification",
    "check_stream_url",
    "get_now_playing_snapshot",
    "match_capsule_against_now_playing",
    "verify_uploaded_media_if_supported",
]

"""M4-A8.4.3 — Async owner cockpit voice (Edge TTS queue + phrase cache, not broadcast)."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_SPEAK_CHARS = 1200
DEFAULT_VOICE = "hi-IN-SwaraNeural"
PURPOSE_OWNER_COCKPIT = "owner_cockpit"
_MIN_AUDIO_BYTES = 1024
_CLEANUP_MAX_AGE_SEC = 3600

_PRIORITY_RANK = {
    "test_voice": 0,
    "error": 1,
    "timeout": 1,
    "final": 2,
    "progress": 5,
}

COMMON_PHRASES = (
    "Neena voice test successful. Main aapko bolkar updates dungi.",
    "Status check kar rahi hoon.",
    "Diagnostics chala rahi hoon.",
    "Stream verification start kar di hai.",
    "Command timeout ho gaya.",
    "Script ready hai. Review ke liye Neena Lab me bhej diya hai.",
)

_ROOT = Path(__file__).resolve().parent.parent.parent
_AUDIO_DIR = _ROOT / "scratch" / "temp" / "cockpit_voice"

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_phrase_index: dict[str, dict[str, Any]] = {}
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cockpit-voice")
_queue_lock = threading.Lock()
_queued_job_ids: list[str] = []


def _edge_tts_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def _sanitize_text(text: str) -> str:
    clean = re.sub(r"\*.*?\*", "", text or "")
    clean = re.sub(r"\[SCRIPT_OUTPUT\][\s\S]*?\[/SCRIPT_OUTPUT\]", "", clean)
    clean = " ".join(clean.split())
    return clean[:MAX_SPEAK_CHARS].strip()


def _text_cache_key(clean: str) -> str:
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _cache_file_id(cache_key: str) -> str:
    return f"cv_cache_{cache_key}"


def _ensure_audio_dir() -> Path:
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    return _AUDIO_DIR


def _cleanup_old_files() -> None:
    try:
        now = time.time()
        for path in _AUDIO_DIR.glob("cv_*.mp3"):
            try:
                if now - path.stat().st_mtime > _CLEANUP_MAX_AGE_SEC:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError as exc:
        logger.debug("cockpit voice cleanup skipped: %s", exc)


def _audio_url_for_file_id(file_id: str) -> str:
    return f"/api/neena/cockpit-voice/audio/{file_id}"


def _register_cached_phrase(clean: str, file_id: str, file_size: int) -> dict[str, Any]:
    entry = {
        "file_id": file_id,
        "audio_url": _audio_url_for_file_id(file_id),
        "file_size_bytes": file_size,
        "chars": len(clean),
    }
    _phrase_index[_text_cache_key(clean)] = entry
    return entry


def _lookup_cached_phrase(clean: str) -> dict[str, Any] | None:
    key = _text_cache_key(clean)
    entry = _phrase_index.get(key)
    if entry:
        path = _AUDIO_DIR / f"{entry['file_id']}.mp3"
        if path.exists() and path.stat().st_size >= _MIN_AUDIO_BYTES:
            return entry
    cache_id = _cache_file_id(key)
    path = _AUDIO_DIR / f"{cache_id}.mp3"
    if path.exists() and path.stat().st_size >= _MIN_AUDIO_BYTES:
        return _register_cached_phrase(clean, cache_id, path.stat().st_size)
    return None


async def _generate_edge_tts_async(text: str, out_path: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(out_path))


def _generate_mp3_sync(clean: str, out_path: Path, voice: str) -> None:
    asyncio.run(_generate_edge_tts_async(clean, out_path, voice or DEFAULT_VOICE))


def _generate_cockpit_voice_sync(
    clean: str,
    *,
    voice: str = DEFAULT_VOICE,
    use_cache: bool = True,
) -> dict[str, Any]:
    if use_cache:
        cached = _lookup_cached_phrase(clean)
        if cached:
            return {
                "ok": True,
                "provider": "edge_tts",
                "cached": True,
                "audio_url": cached["audio_url"],
                "file_id": cached["file_id"],
                "file_size_bytes": cached["file_size_bytes"],
                "chars": len(clean),
            }

    if not _edge_tts_available():
        return {"ok": False, "reason": "edge_tts_not_available", "message": "Edge TTS not installed."}

    _cleanup_old_files()
    _ensure_audio_dir()
    key = _text_cache_key(clean)
    cache_id = _cache_file_id(key)
    out_path = _AUDIO_DIR / f"{cache_id}.mp3"

    try:
        _generate_mp3_sync(clean, out_path, voice)
    except Exception as exc:
        logger.error("cockpit voice generation failed: %s", type(exc).__name__)
        return {
            "ok": False,
            "reason": "generation_failed",
            "message": f"Voice generation failed ({type(exc).__name__}).",
        }

    if not out_path.exists() or out_path.stat().st_size < _MIN_AUDIO_BYTES:
        return {"ok": False, "reason": "empty_audio", "message": "Generated audio empty or too small."}

    file_size = out_path.stat().st_size
    entry = _register_cached_phrase(clean, cache_id, file_size)
    return {
        "ok": True,
        "provider": "edge_tts",
        "cached": False,
        "audio_url": entry["audio_url"],
        "file_id": entry["file_id"],
        "file_size_bytes": file_size,
        "chars": len(clean),
    }


def _set_job(job_id: str, **fields: Any) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.setdefault(job_id, {})
        job.update(fields)
        return dict(job)


def _get_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _coalesce_progress_jobs(priority: str) -> None:
    if _PRIORITY_RANK.get(priority, 5) >= _PRIORITY_RANK["progress"]:
        return
    with _queue_lock:
        for jid in list(_queued_job_ids):
            job = _get_job(jid)
            if not job or job.get("status") != "queued":
                continue
            if _PRIORITY_RANK.get(job.get("priority") or "progress", 5) >= _PRIORITY_RANK["progress"]:
                _set_job(jid, status="dropped", error_summary="superseded by higher priority voice")
                if jid in _queued_job_ids:
                    _queued_job_ids.remove(jid)


def _run_voice_job(job_id: str, clean: str, voice: str) -> None:
    started = time.perf_counter()
    _set_job(job_id, status="running", started_at=started)
    with _queue_lock:
        if job_id in _queued_job_ids:
            _queued_job_ids.remove(job_id)
    result = _generate_cockpit_voice_sync(clean, voice=voice, use_cache=True)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if result.get("ok"):
        _set_job(
            job_id,
            status="succeeded",
            audio_url=result.get("audio_url"),
            file_size_bytes=result.get("file_size_bytes"),
            cached=bool(result.get("cached")),
            latency_ms=latency_ms,
            error_summary=None,
        )
    else:
        _set_job(
            job_id,
            status="failed",
            error_summary=result.get("reason") or result.get("message") or "generation_failed",
            latency_ms=latency_ms,
        )


def _schedule_job(job_id: str, clean: str, voice: str, priority: str) -> None:
    with _queue_lock:
        _queued_job_ids.append(job_id)
    _worker.submit(_run_voice_job, job_id, clean, voice)


def get_cockpit_voice_status() -> dict[str, Any]:
    edge_ok = _edge_tts_available()
    with _queue_lock:
        queued = len([j for j in _queued_job_ids if (_get_job(j) or {}).get("status") == "queued"])
    return {
        "ok": edge_ok,
        "provider": "edge_tts" if edge_ok else None,
        "edge_tts_available": edge_ok,
        "max_chars": MAX_SPEAK_CHARS,
        "purpose": PURPOSE_OWNER_COCKPIT,
        "mode": "background_jobs",
        "queued_jobs": queued,
        "cached_phrases": len(_phrase_index),
        "reason": None if edge_ok else "edge_tts_not_available",
        "message": (
            "Edge TTS async queue ready for owner cockpit voice."
            if edge_ok
            else "Install edge-tts for cockpit voice fallback (pip install edge-tts)."
        ),
    }


def enqueue_cockpit_voice(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    purpose: str = PURPOSE_OWNER_COCKPIT,
    priority: str = "progress",
) -> dict[str, Any]:
    """Queue voice generation; returns in <1s with job_id or cached audio."""
    t0 = time.perf_counter()
    if purpose != PURPOSE_OWNER_COCKPIT:
        return {"ok": False, "reason": "invalid_purpose", "message": "Only owner_cockpit allowed."}

    clean = _sanitize_text(text)
    if not clean:
        return {"ok": False, "reason": "empty_text", "message": "No speakable text."}

    prio = priority if priority in _PRIORITY_RANK else "progress"
    _coalesce_progress_jobs(prio)

    cached = _lookup_cached_phrase(clean)
    job_id = f"voice_{uuid.uuid4().hex[:12]}"
    if cached:
        _set_job(
            job_id,
            status="succeeded",
            priority=prio,
            text_chars=len(clean),
            audio_url=cached["audio_url"],
            file_size_bytes=cached["file_size_bytes"],
            cached=True,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            error_summary=None,
        )
        return {
            "ok": True,
            "mode": "cached",
            "voice_job_id": job_id,
            "status": "succeeded",
            "audio_url": cached["audio_url"],
            "file_size_bytes": cached["file_size_bytes"],
            "message": "cached voice ready",
            "queue_ms": int((time.perf_counter() - t0) * 1000),
        }

    # Attempt local Piper voice synthesis
    from services.voice.local_service import synthesize_local_speech
    _ensure_audio_dir()
    key = _text_cache_key(clean)
    cache_id = _cache_file_id(key)
    out_path = _AUDIO_DIR / f"{cache_id}.wav"

    logger.info("[LOCAL_VOICE] Initiating Piper neural synthesis for phrase: %s...", clean[:40])
    success = synthesize_local_speech(clean, str(out_path))
    if success and out_path.exists() and out_path.stat().st_size >= _MIN_AUDIO_BYTES:
        file_size = out_path.stat().st_size
        entry = _register_cached_phrase(clean, cache_id, file_size)
        _set_job(
            job_id,
            status="succeeded",
            priority=prio,
            text_chars=len(clean),
            audio_url=entry["audio_url"],
            file_size_bytes=file_size,
            cached=False,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            error_summary=None,
        )
        return {
            "ok": True,
            "mode": "cached",
            "voice_job_id": job_id,
            "status": "succeeded",
            "audio_url": entry["audio_url"],
            "file_size_bytes": file_size,
            "message": "local voice ready",
            "queue_ms": int((time.perf_counter() - t0) * 1000),
        }

    # Fallback to Edge TTS if local synthesis failed and Edge TTS is installed
    if not _edge_tts_available():
        return {
            "ok": False,
            "reason": "local_synthesis_failed_and_no_edge_tts",
            "message": "Local voice synthesis failed and Edge TTS is not available.",
        }

    _set_job(
        job_id,
        status="queued",
        priority=prio,
        text_chars=len(clean),
        created_at=time.time(),
        audio_url=None,
        file_size_bytes=None,
        error_summary=None,
        latency_ms=None,
    )
    _schedule_job(job_id, clean, voice or DEFAULT_VOICE, prio)
    return {
        "ok": True,
        "mode": "background",
        "voice_job_id": job_id,
        "status": "queued",
        "message": "voice generation queued",
        "queue_ms": int((time.perf_counter() - t0) * 1000),
    }


def get_voice_job_status(voice_job_id: str) -> dict[str, Any]:
    job = _get_job(voice_job_id)
    if not job:
        return {"ok": False, "reason": "job_not_found", "voice_job_id": voice_job_id}
    return {
        "ok": True,
        "voice_job_id": voice_job_id,
        "status": job.get("status") or "unknown",
        "audio_url": job.get("audio_url"),
        "error_summary": job.get("error_summary"),
        "file_size_bytes": job.get("file_size_bytes"),
        "latency_ms": job.get("latency_ms"),
        "cached": job.get("cached"),
        "priority": job.get("priority"),
    }


def resolve_audio_path(file_id: str) -> Path | None:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", file_id or "")
    if not safe.startswith("cv_"):
        return None
    path_mp3 = _AUDIO_DIR / f"{safe}.mp3"
    if path_mp3.exists() and path_mp3.is_file():
        return path_mp3
    path_wav = _AUDIO_DIR / f"{safe}.wav"
    if path_wav.exists() and path_wav.is_file():
        return path_wav
    return None


def warm_common_phrase_cache() -> None:
    """Lazy warm cache for common phrases (background, non-blocking)."""
    if not _edge_tts_available():
        return

    def _warm() -> None:
        for phrase in COMMON_PHRASES:
            clean = _sanitize_text(phrase)
            if clean and not _lookup_cached_phrase(clean):
                _generate_cockpit_voice_sync(clean, use_cache=True)

    _worker.submit(_warm)


# Backward-compatible alias for tests calling sync generate directly
def generate_cockpit_voice(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    purpose: str = PURPOSE_OWNER_COCKPIT,
) -> dict[str, Any]:
    if purpose != PURPOSE_OWNER_COCKPIT:
        return {"ok": False, "reason": "invalid_purpose", "message": "Only owner_cockpit allowed."}
    clean = _sanitize_text(text)
    if not clean:
        return {"ok": False, "reason": "empty_text", "message": "No speakable text."}
    return _generate_cockpit_voice_sync(clean, voice=voice, use_cache=True)


__all__ = [
    "COMMON_PHRASES",
    "DEFAULT_VOICE",
    "MAX_SPEAK_CHARS",
    "enqueue_cockpit_voice",
    "generate_cockpit_voice",
    "get_cockpit_voice_status",
    "get_voice_job_status",
    "resolve_audio_path",
    "warm_common_phrase_cache",
]

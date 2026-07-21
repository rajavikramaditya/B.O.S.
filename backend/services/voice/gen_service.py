"""Active TTS/voice generation for approved broadcast capsules (M4-A2 / M4-A3.5)."""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import struct
import sys
import wave

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
ELEVENLABS_MODEL = "eleven_monolingual_v1"
GEMINI_TTS_MODELS = (
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
)
DEFAULT_GEMINI_TTS_VOICE = "Kore"
VOICE_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "playout", "voice_assets")


def get_elevenlabs_key() -> str:
    """Read ElevenLabs key from env or backend/config.json (no secrets logged)."""
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key and "your_" not in key.lower() and "placeholder" not in key.lower():
        return key
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("elevenlabs_api_key", "") or ""
        except Exception:
            pass
    return ""


def get_gemini_api_key() -> str:
    """Reuse Gemini key path from llm_provider_router (no secrets logged)."""
    from services.llm.provider_router import get_gemini_api_key as _get_key

    return _get_key()


def _has_real_api_key(api_key: str) -> bool:
    if not api_key:
        return False
    lowered = api_key.lower()
    return not any(marker in lowered for marker in ["here", "your_", "placeholder", "changeme"])


def _has_real_elevenlabs_key(api_key: str) -> bool:
    return _has_real_api_key(api_key)


def get_tts_provider_preference() -> str:
    """Optional override: gemini_tts | elevenlabs | (empty = auto)."""
    pref = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if pref in ("gemini", "gemini_tts"):
        return "gemini_tts"
    if pref == "elevenlabs":
        return "elevenlabs"
    return pref


def check_audio_provider_readiness() -> dict:
    """Read-only TTS provider readiness (no secrets)."""
    gemini_ok = _has_real_api_key(get_gemini_api_key())
    eleven_ok = _has_real_elevenlabs_key(get_elevenlabs_key())
    preference = get_tts_provider_preference() or "(auto)"
    can_real = gemini_ok or eleven_ok

    if preference == "elevenlabs" and eleven_ok:
        active = "elevenlabs"
    elif preference == "gemini_tts" and gemini_ok:
        active = "gemini_tts"
    elif gemini_ok:
        active = "gemini_tts"
    elif eleven_ok:
        active = "elevenlabs"
    else:
        active = "simulated_only"

    missing: list[str] = []
    if not gemini_ok:
        missing.append("GEMINI_API_KEY (for Gemini TTS)")
    if not eleven_ok:
        missing.append("ELEVENLABS_API_KEY (optional fallback)")

    return {
        "elevenlabs_configured": eleven_ok,
        "gemini_tts_configured": gemini_ok,
        "gemini_tts_implemented": True,
        "active_provider": active,
        "provider_preference": preference,
        "can_produce_real_audio": can_real,
        "tts_status": "real_available" if can_real else "simulated_only",
        "missing_for_real": [] if can_real else ["GEMINI_API_KEY or ELEVENLABS_API_KEY"],
    }


def _resolve_voice_id() -> str:
    voice_id = DEFAULT_VOICE_ID
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT elevenlabs_voice_id FROM voice_personas WHERE id = 'rj_neena' AND active = 1"
        )
        row = cursor.fetchone()
        conn.close()
        if row and row["elevenlabs_voice_id"]:
            voice_id = row["elevenlabs_voice_id"]
    except Exception:
        pass
    return voice_id


def _resolve_provider_chain(explicit: str | None = None) -> list[str]:
    pref = (explicit or get_tts_provider_preference() or "").lower()
    if pref == "elevenlabs":
        return ["elevenlabs", "gemini_tts"]
    if pref in ("gemini", "gemini_tts"):
        return ["gemini_tts", "elevenlabs"]
    return ["gemini_tts", "elevenlabs"]


def _write_playable_simulated_wav(filepath: str, duration_sec: float = 1.5) -> None:
    """Short valid WAV tone — browser-playable, not production broadcast audio."""
    sample_rate = 22050
    n_frames = int(sample_rate * duration_sec)
    frames = bytearray()
    for i in range(n_frames):
        val = int(32767 * 0.12 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(struct.pack("<h", val))
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def _write_pcm_as_wav(filepath: str, pcm_bytes: bytes, sample_rate: int = 24000) -> None:
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _parse_pcm_sample_rate(mime_type: str | None) -> int:
    if not mime_type:
        return 24000
    match = re.search(r"rate=(\d+)", mime_type)
    if match:
        return int(match.group(1))
    return 24000


def _render_gemini_tts(text: str, wav_path: str) -> dict:
    """Gemini TTS via REST generateContent — returns playable WAV on success."""
    api_key = get_gemini_api_key()
    if not _has_real_api_key(api_key):
        return {"success": False, "error": "Gemini API key missing"}

    voice_name = os.environ.get("GEMINI_TTS_VOICE", DEFAULT_GEMINI_TTS_VOICE)
    models = [os.environ.get("GEMINI_TTS_MODEL", "").strip()] if os.environ.get("GEMINI_TTS_MODEL") else []
    models.extend(m for m in GEMINI_TTS_MODELS if m not in models)

    payload_base = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    last_error = "Gemini TTS unavailable"
    for model in models:
        if not model:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            res = requests.post(url, headers=headers, json=payload_base, timeout=90.0)
            if res.status_code != 200:
                last_error = f"Gemini TTS HTTP {res.status_code} ({model})"
                logger.warning("Gemini TTS %s: %s", model, res.text[:200])
                continue
            body = res.json()
            candidates = body.get("candidates") or []
            if not candidates:
                last_error = f"Gemini TTS empty response ({model})"
                continue
            parts = (candidates[0].get("content") or {}).get("parts") or []
            inline = None
            for part in parts:
                if part.get("inlineData") or part.get("inline_data"):
                    inline = part.get("inlineData") or part.get("inline_data")
                    break
            if not inline or not inline.get("data"):
                last_error = f"Gemini TTS no audio data ({model})"
                continue
            pcm = base64.b64decode(inline["data"])
            if len(pcm) < 128:
                last_error = f"Gemini TTS audio too short ({model})"
                continue
            sample_rate = _parse_pcm_sample_rate(inline.get("mimeType") or inline.get("mime_type"))
            _write_pcm_as_wav(wav_path, pcm, sample_rate)
            return {
                "success": True,
                "provider": "gemini_tts",
                "model": model,
                "voice_name": voice_name,
                "audio_file_path": wav_path,
                "sample_rate": sample_rate,
            }
        except Exception as exc:
            last_error = f"Gemini TTS error ({model}): {exc}"
            logger.error(last_error)

    return {"success": False, "error": last_error}


def _render_elevenlabs_tts(text: str, mp3_path: str, voice_id: str, api_key: str) -> dict:
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        res = requests.post(url, json=payload, headers=headers, timeout=45.0)
        if res.status_code == 200 and res.content and len(res.content) > 128:
            with open(mp3_path, "wb") as f:
                f.write(res.content)
            return {
                "success": True,
                "provider": "elevenlabs",
                "model": ELEVENLABS_MODEL,
                "voice_id": voice_id,
                "audio_file_path": mp3_path,
            }
        return {
            "success": False,
            "error": f"ElevenLabs returned status {res.status_code}",
        }
    except Exception as exc:
        logger.error("ElevenLabs call failed: %s", exc)
        return {"success": False, "error": f"ElevenLabs call failed: {exc}"}


def validate_audio_file(filepath: str, format_hint: str | None = None) -> dict:
    """
    Byte-level format validation and integrity checks for WAV/MP3 files.
    Enforces duration thresholds, file size constraints, and correct structural signatures.
    """
    if not filepath or not os.path.exists(filepath):
        return {"valid": False, "error": "File does not exist or filepath is empty"}

    file_size = os.path.getsize(filepath)
    # Require a minimum non-trivial file size (e.g., > 128 bytes)
    if file_size <= 128:
        return {"valid": False, "error": f"File is too small ({file_size} bytes), likely empty or truncated"}

    # Determine format based on format_hint or extension
    fmt = (format_hint or "").lower()
    if not fmt:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".wav":
            fmt = "wav"
        elif ext in (".mp3", ".mpeg"):
            fmt = "mp3"
        else:
            fmt = "wav"  # fallback

    if fmt == "wav":
        try:
            with wave.open(filepath, "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                nframes = wf.getnframes()
                
                if nframes <= 0:
                    return {"valid": False, "error": "WAV file contains 0 frames"}
                if sample_rate <= 0:
                    return {"valid": False, "error": "WAV file has invalid sample rate (<=0)"}
                if channels <= 0:
                    return {"valid": False, "error": "WAV file has invalid channels (<=0)"}
                    
                duration = nframes / float(sample_rate)
                if duration < 0.2:
                    return {"valid": False, "error": f"WAV file duration too short ({duration:.3f}s, min 0.2s)"}
                    
                return {
                    "valid": True,
                    "format": "wav",
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "frame_count": nframes,
                    "duration": round(duration, 3),
                    "file_size": file_size
                }
        except Exception as exc:
            return {"valid": False, "error": f"Failed to parse WAV headers: {exc}"}

    elif fmt == "mp3":
        try:
            with open(filepath, "rb") as f:
                header = f.read(1024)
                if not header or len(header) < 128:
                    return {"valid": False, "error": "File content too short to validate MP3 structure"}
                
                # Check for ID3 tag
                if header.startswith(b'ID3') and len(header) >= 10:
                    size_bytes = header[6:10]
                    id3_size = (
                        (size_bytes[0] & 0x7F) << 21 |
                        (size_bytes[1] & 0x7F) << 14 |
                        (size_bytes[2] & 0x7F) << 7  |
                        (size_bytes[3] & 0x7F)
                    )
                    has_footer = bool(header[5] & 0x10)
                    total_id3_size = 10 + id3_size + (10 if has_footer else 0)
                    
                    f.seek(total_id3_size)
                    header = f.read(1024)
                
                # Scan for MPEG Frame Sync: 0xFF followed by byte matching & 0xE0 == 0xE0
                found_sync = False
                for idx in range(len(header) - 1):
                    if header[idx] == 0xFF and (header[idx + 1] & 0xE0) == 0xE0:
                        found_sync = True
                        break
                        
                if not found_sync:
                    return {"valid": False, "error": "No valid MPEG frame sync sequence found after ID3 header"}
                
                duration = None
                duration_unknown = True
                try:
                    # Attempt using mutagen if available
                    from mutagen.mp3 import MP3
                    audio = MP3(filepath)
                    duration = audio.info.length
                    if duration is not None:
                        duration_unknown = False
                        if duration < 0.2:
                            return {"valid": False, "error": f"MP3 duration too short ({duration:.3f}s, min 0.2s)"}
                except Exception:
                    pass

                return {
                    "valid": True,
                    "format": "mp3",
                    "channels": 1,
                    "sample_rate": 24000,
                    "duration": round(duration, 3) if duration is not None else None,
                    "duration_unknown": duration_unknown,
                    "file_size": file_size
                }
        except Exception as exc:
            return {"valid": False, "error": f"Failed to parse MP3 structure: {exc}"}

    return {"valid": False, "error": f"Unsupported audio format: {fmt}"}


def safe_delete_invalid_file(filepath: str) -> None:
    """
    Safely deletes a file only if it is located inside the approved VOICE_ASSETS_DIR.
    Prevents path traversal, absolute path deletes, or arbitrary system file manipulation.
    """
    if not filepath or not os.path.exists(filepath):
        return
        
    from pathlib import Path
    try:
        abs_assets = Path(VOICE_ASSETS_DIR).resolve()
        abs_file = Path(filepath).resolve()
        abs_file.relative_to(abs_assets)
        if abs_file.exists():
            abs_file.unlink()
            logger.info("Safely deleted invalid generated audio file: %s", abs_file)
    except (ValueError, OSError) as exc:
        logger.warning("Safety block: Attempted to delete file outside approved directory: %s (%s)", filepath, exc)


def _public_audio_url(filepath: str | None) -> str | None:
    if not filepath or not os.path.exists(filepath):
        return None
    return f"/playout/voice_assets/{os.path.basename(filepath)}"


def render_script_audio(
    script_id: int,
    text: str,
    voice_id: str | None = None,
    *,
    filename_stem: str | None = None,
    link_capsule: bool = True,
    provider: str | None = None,
) -> dict:
    """
    Generate audio for an approved script.
    Provider order: explicit preference → Gemini TTS → ElevenLabs → simulated WAV.
    """
    os.makedirs(VOICE_ASSETS_DIR, exist_ok=True)
    voice_id = voice_id or _resolve_voice_id()
    stem = filename_stem or f"voice_asset_{script_id or int(os.urandom(2).hex(), 16)}"
    char_count = len(text or "")

    result = {
        "script_id": script_id,
        "voice_id": voice_id,
        "preview_type": "preview",
        "production_asset": False,
        "provider": "unknown",
        "truth_level": "unknown",
        "audio_truth_level": "failed",
        "status": "unavailable",
        "audio_file_path": None,
        "audio_url": None,
        "message": "",
    }

    if not (text or "").strip():
        result["message"] = "Script text is empty; audio was not generated."
        result["audio_truth_level"] = "failed"
        return result

    mp3_path = os.path.join(VOICE_ASSETS_DIR, f"{stem}.mp3")
    wav_path = os.path.join(VOICE_ASSETS_DIR, f"{stem}.wav")
    errors: list[str] = []

    for provider_name in _resolve_provider_chain(provider):
        if provider_name == "gemini_tts" and _has_real_api_key(get_gemini_api_key()):
            gem = _render_gemini_tts(text, wav_path)
            if gem.get("success"):
                val = validate_audio_file(wav_path, "wav")
                if not val.get("valid"):
                    safe_delete_invalid_file(wav_path)
                    errors.append(f"Gemini TTS audio validation failed: {val.get('error')}")
                    continue

                audio_metadata = {
                    "file_size": val.get("file_size"),
                    "duration": val.get("duration"),
                    "format": val.get("format"),
                    "sample_rate": val.get("sample_rate"),
                    "channels": val.get("channels"),
                    "duration_unknown": val.get("duration_unknown", False)
                }

                result.update(
                    {
                        "status": "real_tts_ready",
                        "truth_level": "real",
                        "audio_truth_level": "real",
                        "production_asset": True,
                        "preview_type": "production",
                        "provider": "gemini_tts",
                        "audio_file_path": wav_path,
                        "audio_url": _public_audio_url(wav_path),
                        "message": "Real Gemini TTS audio generated and validated.",
                        "audio_metadata": audio_metadata,
                    }
                )
                db.add_voice_asset(script_id, voice_id, text, wav_path, "production_real")
                db.add_activity_log("tts", f"Real Gemini TTS for script {script_id}: {char_count} chars")
                if link_capsule and script_id:
                    _link_capsule_audio(
                        script_id,
                        wav_path,
                        "real",
                        provider_meta={
                            "provider": "gemini_tts",
                            "model": gem.get("model"),
                            "voice_name": gem.get("voice_name"),
                            "production_asset": True,
                        },
                        audio_metadata=audio_metadata,
                    )
                return result
            errors.append(gem.get("error", "Gemini TTS failed"))

        if provider_name == "elevenlabs":
            api_key = get_elevenlabs_key()
            if _has_real_elevenlabs_key(api_key):
                el = _render_elevenlabs_tts(text, mp3_path, voice_id, api_key)
                if el.get("success"):
                    val = validate_audio_file(mp3_path, "mp3")
                    if not val.get("valid"):
                        safe_delete_invalid_file(mp3_path)
                        errors.append(f"ElevenLabs audio validation failed: {val.get('error')}")
                        continue

                    audio_metadata = {
                        "file_size": val.get("file_size"),
                        "duration": val.get("duration"),
                        "format": val.get("format"),
                        "sample_rate": val.get("sample_rate"),
                        "channels": val.get("channels"),
                        "duration_unknown": val.get("duration_unknown", False)
                    }

                    result.update(
                        {
                            "status": "real_tts_ready",
                            "truth_level": "real",
                            "audio_truth_level": "real",
                            "production_asset": True,
                            "preview_type": "production",
                            "provider": "elevenlabs",
                            "audio_file_path": mp3_path,
                            "audio_url": _public_audio_url(mp3_path),
                            "message": "Real ElevenLabs audio generated and validated.",
                            "audio_metadata": audio_metadata,
                        }
                    )
                    estimated_cost = round((char_count / 1000.0) * 0.30, 4)
                    db.add_voice_asset(script_id, voice_id, text, mp3_path, "production_real")
                    db.log_voice_usage(voice_id, char_count, estimated_cost)
                    db.add_activity_log("tts", f"Real ElevenLabs for script {script_id}: {char_count} chars")
                    if link_capsule and script_id:
                        _link_capsule_audio(
                            script_id,
                            mp3_path,
                            "real",
                            provider_meta={
                                "provider": "elevenlabs",
                                "model": ELEVENLABS_MODEL,
                                "voice_id": voice_id,
                                "production_asset": True,
                            },
                            audio_metadata=audio_metadata,
                        )
                    return result
                errors.append(el.get("error", "ElevenLabs failed"))

    allow_sim = os.environ.get("ALLOW_SIMULATED_TTS_DEV_ONLY", "false").lower() in ("true", "1", "yes")
    if not allow_sim:
        hint = errors[0] if errors else "No real TTS provider configured."
        result.update(
            {
                "status": "unavailable",
                "truth_level": "failed",
                "audio_truth_level": "failed",
                "production_asset": False,
                "audio_file_path": None,
                "audio_url": None,
                "message": f"Real TTS available nahi hai. {hint}",
            }
        )
        if link_capsule and script_id:
            _link_capsule_audio(
                script_id,
                None,
                "failed",
                provider_meta={"provider": "none", "production_asset": False, "error_message": hint},
            )
        return result

    _write_playable_simulated_wav(wav_path)
    val = validate_audio_file(wav_path, "wav")
    if not val.get("valid"):
        safe_delete_invalid_file(wav_path)
        err_msg = f"Simulated WAV validation failed: {val.get('error')}"
        result.update(
            {
                "status": "unavailable",
                "truth_level": "failed",
                "audio_truth_level": "failed",
                "production_asset": False,
                "audio_file_path": None,
                "audio_url": None,
                "message": err_msg,
            }
        )
        if link_capsule and script_id:
            _link_capsule_audio(
                script_id,
                None,
                "failed",
                provider_meta={"provider": "none", "production_asset": False, "error_message": err_msg},
            )
        return result

    audio_metadata = {
        "file_size": val.get("file_size"),
        "duration": val.get("duration"),
        "format": val.get("format"),
        "sample_rate": val.get("sample_rate"),
        "channels": val.get("channels"),
        "duration_unknown": val.get("duration_unknown", False)
    }

    hint = errors[0] if errors else "No real TTS provider configured."
    result.update(
        {
            "status": "simulated_preview",
            "truth_level": "simulated",
            "audio_truth_level": "simulated",
            "production_asset": False,
            "preview_type": "preview",
            "provider": "local_simulated_wav",
            "audio_file_path": wav_path,
            "audio_url": _public_audio_url(wav_path),
            "message": f"{hint} Simulated preview WAV created.",
            "audio_metadata": audio_metadata,
        }
    )
    db.add_voice_asset(script_id, voice_id, text, wav_path, "preview_simulated")
    db.add_activity_log("tts", f"Simulated playable preview for script {script_id}")
    if link_capsule and script_id:
        _link_capsule_audio(
            script_id,
            wav_path,
            "simulated",
            provider_meta={"provider": "local_simulated_wav", "production_asset": False},
            audio_metadata=audio_metadata,
        )
    return result


def _link_capsule_audio(
    approval_queue_id: int,
    audio_file_path: str | None,
    audio_truth_level: str,
    provider_meta: dict | None = None,
    audio_metadata: dict | None = None,
) -> None:
    from services.broadcast.capsule_service import update_capsule_audio_status

    truth_level = "real" if audio_truth_level == "real" else "simulated"
    update_capsule_audio_status(
        approval_queue_id,
        audio_file_path,
        audio_truth_level,
        truth_level=truth_level,
        metadata_patch=provider_meta,
        audio_metadata=audio_metadata,
    )


def render_approved_script(script_id: int, voice_id: str, text: str) -> dict:
    """Backward-compatible wrapper for approval-queue voice preview endpoint."""
    return render_script_audio(
        script_id,
        text,
        voice_id=voice_id,
        filename_stem=f"voice_asset_{script_id}",
        link_capsule=True,
    )


def generate_capsule_audio(capsule_id: int, *, regenerate: bool = False) -> dict:
    """M4-A2 main flow: approved capsule → playable audio → capsule status update."""
    from services.broadcast.capsule_service import (
        AUDIO_APPROVAL_BLOCKED_MESSAGE,
        get_capsule_by_id,
        update_capsule_audio_status,
        validate_capsule_for_audio_generation,
    )

    gate = validate_capsule_for_audio_generation(capsule_id, regenerate=regenerate)
    if not gate.get("allowed"):
        return {
            "success": False,
            "blocked": True,
            "capsule_id": capsule_id,
            "message": gate.get("message", AUDIO_APPROVAL_BLOCKED_MESSAGE),
            "audio_truth_level": "none",
            "production_asset": False,
        }

    capsule = gate["capsule"]
    readiness = check_audio_provider_readiness()
    if not readiness.get("can_produce_real_audio"):
        allow_sim = os.environ.get("ALLOW_SIMULATED_TTS_DEV_ONLY", "false").lower() in ("true", "1", "yes")
        if not allow_sim:
            return {
                "success": False,
                "blocked": True,
                "capsule_id": capsule_id,
                "message": "Real TTS available nahi hai, broadcast audio generate nahi kar sakti.",
                "audio_truth_level": "failed",
                "production_asset": False,
            }

    approval_id = capsule["approval_queue_id"]
    if capsule.get("audio_file_path") and not regenerate:
        if capsule.get("audio_truth_level") in ("real", "simulated"):
            meta = capsule.get("metadata") or {}
            is_real = capsule.get("audio_truth_level") == "real"
            return {
                "success": True,
                "capsule_id": capsule_id,
                "approval_status": capsule.get("approval_status"),
                "audio_truth_level": capsule.get("audio_truth_level"),
                "audio_file_path": capsule.get("audio_file_path"),
                "audio_url": _public_audio_url(capsule.get("audio_file_path")),
                "provider": meta.get("provider", "unknown"),
                "production_asset": is_real,
                "message": "Audio already exists. Use regenerate-audio to replace.",
                "azuracast_status": capsule.get("azuracast_status", "blocked"),
            }

    render = render_script_audio(
        approval_id,
        capsule.get("script_text", ""),
        filename_stem=f"capsule_{capsule_id}",
        link_capsule=True,
    )

    if not render.get("audio_file_path"):
        update_capsule_audio_status(
            approval_id,
            None,
            "failed",
            truth_level="failed",
            error_message=render.get("message") or "TTS provider missing",
        )
        return {
            "success": False,
            "capsule_id": capsule_id,
            "approval_status": "approved",
            "audio_truth_level": "failed",
            "production_asset": False,
            "message": render.get("message", "Audio generation failed."),
            "error": render.get("message"),
        }

    updated = get_capsule_by_id(capsule_id) or capsule
    is_real = render.get("audio_truth_level") == "real"
    return {
        "success": True,
        "capsule_id": capsule_id,
        "approval_status": updated.get("approval_status"),
        "audio_truth_level": render.get("audio_truth_level"),
        "audio_status": render.get("status"),
        "audio_file_path": render.get("audio_file_path"),
        "audio_url": render.get("audio_url"),
        "provider": render.get("provider"),
        "production_asset": is_real,
        "truth_level": render.get("truth_level"),
        "message": render.get("message"),
        "azuracast_status": updated.get("azuracast_status", "blocked"),
        "stream_verification_status": updated.get("stream_verification_status", "unknown"),
    }


def get_broadcast_audio_readiness() -> dict:
    """Combined audio + AzuraCast push readiness (no secrets)."""
    from services.broadcast.azuracast_client import check_azuracast_write_config

    audio = check_audio_provider_readiness()
    az = check_azuracast_write_config()
    real_push_ready = (
        audio.get("can_produce_real_audio")
        and az.get("ready_for_real_push")
    )
    blockers: list[str] = []
    if not audio.get("can_produce_real_audio"):
        blockers.extend(audio.get("missing_for_real") or [])
    if not az.get("ready_for_real_push"):
        blockers.extend(az.get("missing_config") or az.get("missing") or [])

    return {
        "audio": audio,
        "azuracast": az,
        "real_push_ready": real_push_ready,
        "blockers": blockers,
        "m4_a4_note": "Stream verification M4-A4 tabhi chalega jab real AzuraCast push success hoga.",
    }


__all__ = [
    "get_elevenlabs_key",
    "get_gemini_api_key",
    "check_audio_provider_readiness",
    "get_broadcast_audio_readiness",
    "render_script_audio",
    "render_approved_script",
    "generate_capsule_audio",
]

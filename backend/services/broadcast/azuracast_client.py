import os
import json
import base64
import httpx
import logging
import asyncio
import requests
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

# --- Helpers to read config without old IP fallbacks ---

def _get_config_json() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _env_or_config(env_key: str, config_key: str) -> str:
    val = os.environ.get(env_key, "")
    if _is_configured(val):
        return val.strip()
    cfg = _get_config_json().get(config_key, "")
    return str(cfg).strip() if cfg else ""


def _get_base_url():
    """Return AZURACAST_BASE_URL from env, or empty string if not configured."""
    return _env_or_config("AZURACAST_BASE_URL", "azuracast_base_url")


def _get_stream_url():
    """Return AZURACAST_STREAM_URL from env, or empty string if not configured."""
    return _env_or_config("AZURACAST_STREAM_URL", "azuracast_stream_url")


def _get_public_page():
    """Return AZURACAST_PUBLIC_PAGE from env, or empty string if not configured."""
    return _env_or_config("AZURACAST_PUBLIC_PAGE", "azuracast_public_page")


def _get_station_id():
    return _env_or_config("AZURACAST_STATION_ID", "azuracast_station_id") or "1"


def _get_station_shortcode() -> str:
    return _env_or_config("AZURACAST_STATION_SHORTCODE", "azuracast_station_shortcode")


def _get_api_key() -> str:
    return _env_or_config("AZURACAST_API_KEY", "azuracast_api_key")


def _get_playlist_id() -> str:
    return _env_or_config("AZURACAST_PLAYLIST_ID", "azuracast_playlist_id")


def _get_target_folder() -> str:
    return _env_or_config("AZURACAST_TARGET_FOLDER", "azuracast_target_folder")


def _get_push_mode() -> str:
    return os.environ.get("AZURACAST_PUSH_MODE", "").strip().lower()


def azuracast_writes_enabled() -> bool:
    """Kill-switch for real AzuraCast write APIs (upload/playlist/queue).

    Default OFF so deploy is safe. Owner sets AZURACAST_WRITES_ENABLED=true on VM
    after config is verified. Owner confirmation / safety kernel still required
    for send_azuracast — this flag only removes the old M4-A1 hard-return.
    """
    raw = (os.environ.get("AZURACAST_WRITES_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _writes_hard_block(action: str) -> dict:
    return {
        "success": False,
        "error": (
            f"AzuraCast {action} blocked: set AZURACAST_WRITES_ENABLED=true on the VM "
            "after write-config is ready (owner confirm still required for push)."
        ),
        "writes_enabled": False,
        "azuracast_status": "blocked",
    }


def _api_verify_ssl() -> bool:
    verify_base = get_ssl_verify()
    if not verify_base:
        return False
    val = os.environ.get("AZURACAST_API_VERIFY_SSL", "")
    if val:
        return val.lower() in ("1", "true", "yes")
    # Docker/loopback HTTPS often uses a public-DNS cert (SAN mismatch on host.docker.internal).
    base = (_get_base_url() or "").lower()
    if any(h in base for h in ("host.docker.internal", "127.0.0.1", "localhost")):
        return False
    return True


def _is_configured(url: str) -> bool:
    """Check if a URL value looks like a real configured value (not placeholder/empty)."""
    if not url:
        return False
    lower = url.lower()
    return not ("here" in lower or "your_" in lower or "placeholder" in lower)


async def fetch_public_stream_stats() -> dict:
    """
    Queries public API GET /api/nowplaying/orai_radio
    Returns {"online": True, "title": "...", "listeners": 0}
    """
    base_url = _get_base_url()
    if not _is_configured(base_url):
        return {"online": False, "title": "Unconfigured", "listeners": 0, "truth_level": "unknown"}

    api_url = f"{base_url.rstrip('/')}/api/nowplaying/orai_radio"
    try:
        async with httpx.AsyncClient(timeout=3.0, verify=_api_verify_ssl()) as client:
            res = await client.get(api_url)
            if res.status_code == 200:
                data = res.json()
                current_song = data.get("now_playing", {}).get("song", {})
                title = current_song.get("title", "Unknown")
                artist = current_song.get("artist", "Unknown")
                listeners = data.get("listeners", {}).get("total", 0)
                song_title = f"{artist} - {title}" if artist and artist != "Unknown" else title
                return {
                    "online": True,
                    "title": song_title,
                    "listeners": listeners,
                    "truth_level": "real_verified"
                }
            else:
                return {"online": False, "title": "Offline", "listeners": 0, "truth_level": "failed"}
    except Exception as e:
        logger.error(f"Error fetching public stream stats: {e}")
        return {"online": False, "title": "Offline", "listeners": 0, "truth_level": "failed"}


async def async_get_azuracast_status() -> dict:
    """
    Asynchronously queries AzuraCast status, public pages, and now playing details
    using HTTPX AsyncClient with strict timeouts to prevent system blocking.
    """
    base_url = _get_base_url()
    station_id = _get_station_id()
    public_page = _get_public_page()
    stream_url = _get_stream_url()

    status = {
        "configured": _is_configured(base_url),
        "base_url": base_url or "(not set)",
        "station_id": station_id,
        "public_page": public_page or "(not set)",
        "stream_url": stream_url or "(not set)",
        "stream_reachable": False,
        "public_page_reachable": False,
        "icecast_status": "unknown",
        "autodj_status": "unknown",
        "admin_control_available": False,
        "listener_count": 0,
        "now_playing_title": "Unknown",
        "now_playing_artist": "Unknown",
        "truth_level": "unknown",
        "notes": []
    }

    if not status["configured"]:
        status["notes"].append("AzuraCast base URL is not configured in environment.")
        status["truth_level"] = "unknown"
        return status

    async with httpx.AsyncClient(timeout=3.0, verify=_api_verify_ssl()) as client:
        # 1. Check Stream Reachability
        # NOTE: radio stream is an endless live audio body. A plain GET would read it
        # into memory forever (memory/network leak). Use a streamed request and only
        # inspect the status line/headers, then close without consuming the body.
        if _is_configured(stream_url):
            try:
                async with client.stream("GET", stream_url, follow_redirects=True) as res:
                    status["stream_reachable"] = res.status_code in [200, 206]
                    status["icecast_status"] = "running" if status["stream_reachable"] else "offline"
            except Exception as e:
                status["notes"].append(f"Stream check failed: {str(e)}")
                status["icecast_status"] = "offline"
        else:
            status["notes"].append("Stream URL is not configured.")

        # 2. Check Public Page Reachability
        if _is_configured(public_page):
            try:
                res = await client.get(public_page, follow_redirects=True)
                status["public_page_reachable"] = res.status_code in [200, 301, 302]
            except Exception as e:
                status["notes"].append(f"Public page check failed: {str(e)}")

        # 3. Fetch NowPlaying API from AzuraCast
        try:
            api_url = f"{base_url.rstrip('/')}/api/nowplaying/{station_id}"
            res = await client.get(api_url)
            if res.status_code == 200:
                data = res.json()
                status["icecast_status"] = "running"
                status["autodj_status"] = "running"
                status["listener_count"] = data.get("listeners", {}).get("total", 0)
                
                current_song = data.get("now_playing", {}).get("song", {})
                status["now_playing_title"] = current_song.get("title", "Unknown")
                status["now_playing_artist"] = current_song.get("artist", "Unknown")
                status["truth_level"] = "real_verified"
            else:
                status["notes"].append(f"AzuraCast NowPlaying API returned status code {res.status_code}")
                # Live mount beats metadata API — do not call a reachable stream "failed".
                if status.get("stream_reachable"):
                    status["truth_level"] = "stream_reachable"
                    status["notes"].append("Stream mount reachable; nowplaying metadata unavailable.")
                else:
                    status["truth_level"] = "failed"
        except Exception as e:
            status["notes"].append(f"Failed to query AzuraCast NowPlaying API: {str(e)}")
            if status.get("stream_reachable"):
                status["truth_level"] = "stream_reachable"
            else:
                status["truth_level"] = "failed"

    # Admin write available when API key is configured (read-only flag, no secret exposed)
    status["admin_control_available"] = bool(_get_api_key()) and _is_configured(_get_api_key())
    if not status["admin_control_available"]:
        status["notes"].append("Admin controls (restart, playlists) are not available without server-level credentials.")

    return status

def get_azuracast_status() -> dict:
    """
    Synchronous wrapper for backwards compatibility.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # If event loop is already running, use a synchronous fallback to prevent nesting exceptions
        import requests
        base_url = _get_base_url()
        station_id = _get_station_id()
        public_page = _get_public_page()
        stream_url = _get_stream_url()

        status = {
            "configured": _is_configured(base_url),
            "base_url": base_url or "(not set)",
            "station_id": station_id,
            "public_page": public_page or "(not set)",
            "stream_url": stream_url or "(not set)",
            "stream_reachable": False,
            "public_page_reachable": False,
            "icecast_status": "unknown",
            "autodj_status": "unknown",
            "admin_control_available": False,
            "listener_count": 0,
            "now_playing_title": "Unknown",
            "now_playing_artist": "Unknown",
            "truth_level": "unknown",
            "notes": []
        }

        if not status["configured"]:
            status["notes"].append("AzuraCast base URL is not configured in environment.")
            return status

        if _is_configured(stream_url):
            try:
                res = requests.get(stream_url, stream=True, timeout=2.0)
                status["stream_reachable"] = res.status_code in [200, 206]
                status["icecast_status"] = "running" if status["stream_reachable"] else "offline"
                res.close()
            except Exception:
                status["icecast_status"] = "offline"

        if _is_configured(public_page):
            try:
                res = requests.get(public_page, timeout=2.0)
                status["public_page_reachable"] = res.status_code in [200, 301, 302]
            except Exception:
                pass

        try:
            api_url = f"{base_url.rstrip('/')}/api/nowplaying/{station_id}"
            res = requests.get(api_url, timeout=2.0, verify=_api_verify_ssl())
            if res.status_code == 200:
                data = res.json()
                status["icecast_status"] = "running"
                status["autodj_status"] = "running"
                status["listener_count"] = data.get("listeners", {}).get("total", 0)
                current_song = data.get("now_playing", {}).get("song", {})
                status["now_playing_title"] = current_song.get("title", "Unknown")
                status["now_playing_artist"] = current_song.get("artist", "Unknown")
                status["truth_level"] = "real_verified"
            elif status.get("stream_reachable"):
                status["truth_level"] = "stream_reachable"
                status["notes"].append(f"nowplaying_http_{res.status_code}; stream mount OK")
        except Exception:
            if status.get("stream_reachable"):
                status["truth_level"] = "stream_reachable"
        status["admin_control_available"] = bool(_get_api_key()) and _is_configured(_get_api_key())
        return status
    else:
        return loop.run_until_complete(async_get_azuracast_status())


# ---------------------------------------------------------------------------
# M4-A3 — AzuraCast write / media upload (real API or explicit local_simulated)
# ---------------------------------------------------------------------------

def check_azuracast_write_config() -> dict:
    """Report write readiness without exposing secrets."""
    base_url = _get_base_url()
    api_key = _get_api_key()
    station_id = _get_station_id()
    shortcode = _get_station_shortcode()
    playlist_id = _get_playlist_id()
    target_folder = _get_target_folder()
    push_mode = _get_push_mode()

    present = {
        "AZURACAST_BASE_URL": _is_configured(base_url),
        "AZURACAST_STATION_ID": bool(station_id),
        "AZURACAST_STATION_SHORTCODE": bool(shortcode),
        "AZURACAST_STREAM_URL": _is_configured(_get_stream_url()),
        "AZURACAST_API_KEY": _is_configured(api_key),
        "AZURACAST_PLAYLIST_ID": bool(playlist_id),
        "AZURACAST_TARGET_FOLDER": bool(target_folder),
        "RUNTIME_MODE": bool(os.environ.get("RUNTIME_MODE", "")),
        "AZURACAST_PUSH_MODE": push_mode or "(default real_api)",
    }
    missing = []
    if not present["AZURACAST_BASE_URL"]:
        missing.append("AZURACAST_BASE_URL")
    if not present["AZURACAST_API_KEY"]:
        missing.append("AZURACAST_API_KEY")
    if not present["AZURACAST_STATION_ID"] and not present["AZURACAST_STATION_SHORTCODE"]:
        missing.append("AZURACAST_STATION_ID or AZURACAST_STATION_SHORTCODE")
    if not present["AZURACAST_PLAYLIST_ID"] and not present["AZURACAST_TARGET_FOLDER"]:
        missing.append("AZURACAST_PLAYLIST_ID or AZURACAST_TARGET_FOLDER")

    writes_on = azuracast_writes_enabled()
    if push_mode == "local_simulated":
        mode = "local_simulated"
        ready = True
        ready_for_real_push = False
        target_strategy = "local_simulated"
    elif not missing and writes_on:
        mode = "real_api"
        ready = True
        ready_for_real_push = True
        target_strategy = "playlist" if present["AZURACAST_PLAYLIST_ID"] else "folder"
    elif not missing and not writes_on:
        mode = "writes_disabled"
        ready = False
        ready_for_real_push = False
        target_strategy = "playlist" if present["AZURACAST_PLAYLIST_ID"] else "folder"
        if "AZURACAST_WRITES_ENABLED" not in missing:
            missing = list(missing) + ["AZURACAST_WRITES_ENABLED"]
    else:
        mode = "blocked"
        ready = False
        ready_for_real_push = False
        target_strategy = None

    url_scheme = "http" if (base_url or "").startswith("http://") else ("https" if (base_url or "").startswith("https://") else "unknown")
    ssl_verify_active = _api_verify_ssl() if url_scheme == "https" else False
    security_note = "plain_http_azuracast" if url_scheme == "http" else ("secure_https_azuracast" if url_scheme == "https" else "unconfigured_scheme")

    return {
        "ready": ready,
        "mode": mode,
        "push_mode": mode,
        "ready_for_real_push": ready_for_real_push,
        "writes_enabled": writes_on,
        "target_strategy": target_strategy,
        "base_url_present": present["AZURACAST_BASE_URL"],
        "api_key_present": present["AZURACAST_API_KEY"],
        "station_id_present": bool(present["AZURACAST_STATION_ID"] or present["AZURACAST_STATION_SHORTCODE"]),
        "playlist_id_present": present["AZURACAST_PLAYLIST_ID"],
        "target_folder_present": present["AZURACAST_TARGET_FOLDER"],
        "missing_config": missing,
        "present": present,
        "missing": missing,
        "station_id": station_id if present["AZURACAST_STATION_ID"] else None,
        "has_playlist_target": present["AZURACAST_PLAYLIST_ID"],
        "has_folder_target": present["AZURACAST_TARGET_FOLDER"],
        "api_docs_hint": f"{base_url.rstrip('/')}/api" if present["AZURACAST_BASE_URL"] else None,
        "url_scheme": url_scheme,
        "ssl_verify_active": ssl_verify_active,
        "security_note": security_note,
    }


def get_azuracast_write_status() -> dict:
    """Alias for config check used by diagnostics/lab."""
    return check_azuracast_write_config()


def _api_headers() -> dict:
    key = _get_api_key()
    return {"X-API-Key": key, "Accept": "application/json"}


def _extract_media_id(upload_response: dict) -> str | None:
    if not upload_response:
        return None
    for key in ("id", "unique_id", "song_id", "media_id"):
        if upload_response.get(key):
            return str(upload_response[key])
    links = upload_response.get("links") or {}
    if isinstance(links, dict):
        for key in ("media", "self"):
            if links.get(key):
                return str(links[key])
    return upload_response.get("formatted_path") or upload_response.get("path")


def _normalize_target_folder(folder: str | None) -> str:
    if not folder:
        return ""
    return folder.strip().strip("/")


def upload_media_file(
    file_path: str,
    *,
    station_id: str | None = None,
    target_folder: str | None = None,
) -> dict:
    """Upload audio to AzuraCast station media library via REST API (JSON + base64)."""
    if not azuracast_writes_enabled():
        return _writes_hard_block("upload")

    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    api_key = _get_api_key()
    if not _is_configured(base_url) or not _is_configured(api_key):
        return {"success": False, "error": "AzuraCast blocked: AZURACAST_BASE_URL or AZURACAST_API_KEY missing"}

    url = f"{base_url}/api/station/{station_id}/files"
    headers = {**_api_headers(), "Content-Type": "application/json"}
    folder = _normalize_target_folder(target_folder or _get_target_folder())
    basename = os.path.basename(file_path)
    remote_path = f"{folder}/{basename}" if folder else basename

    try:
        with open(file_path, "rb") as audio_file:
            payload = {
                "path": remote_path,
                "file": base64.b64encode(audio_file.read()).decode("ascii"),
            }
        res = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=90.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code not in (200, 201):
            return {
                "success": False,
                "error": f"AzuraCast upload failed HTTP {res.status_code}",
                "detail": (res.text or "")[:300],
            }
        body = res.json() if res.content else {}
        media_id = _extract_media_id(body)
        return {
            "success": True,
            "media_id": media_id,
            "response_summary": {
                "path": body.get("path") or body.get("formatted_path") or remote_path,
                "name": body.get("name") or basename,
                "target_folder": folder or None,
            },
        }
    except Exception as exc:
        logger.error("AzuraCast upload_media_file failed: %s", exc)
        return {"success": False, "error": f"AzuraCast upload error: {exc}"}


def assign_media_to_playlist_or_folder(
    media_id: str,
    *,
    station_id: str | None = None,
    playlist_id: str | None = None,
    file_path: str | None = None,
) -> dict:
    """Append uploaded media to configured playlist when playlist ID is set."""
    if not azuracast_writes_enabled():
        return _writes_hard_block("playlist assignment")

    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    playlist_id = playlist_id or _get_playlist_id()
    api_key = _get_api_key()

    if not playlist_id:
        folder = _get_target_folder()
        if folder:
            return {
                "success": True,
                "scheduled": False,
                "target_strategy": "folder",
                "target_folder": folder,
                "message": "Media uploaded to folder only; playlist assignment skipped (folder strategy).",
            }
        return {"success": False, "error": "AzuraCast blocked: target playlist/folder config missing"}

    url = f"{base_url}/api/station/{station_id}/playlist/{playlist_id}/append"
    headers = {**_api_headers(), "Content-Type": "application/json"}
    payload = {"id": media_id}
    if file_path:
        payload["path"] = file_path

    try:
        res = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=45.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code not in (200, 201, 204):
            return {
                "success": False,
                "error": f"AzuraCast playlist append failed HTTP {res.status_code}",
                "detail": (res.text or "")[:300],
            }
        return {"success": True, "scheduled": True, "playlist_id": playlist_id, "target_strategy": "playlist"}
    except Exception as exc:
        logger.error("AzuraCast playlist append failed: %s", exc)
        return {"success": False, "error": f"AzuraCast playlist error: {exc}"}


# ---------------------------------------------------------------------------
# M4-A4.5 — Playback / queue read + control
# ---------------------------------------------------------------------------

def get_media_file_info(media_id: str, *, station_id: str | None = None) -> dict:
    """Fetch station media metadata by ID (no secrets)."""
    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    if not _is_configured(base_url) or not _is_configured(_get_api_key()):
        return {"found": False, "error": "azuracast_config_missing"}

    url = f"{base_url}/api/station/{station_id}/file/{media_id}"
    try:
        res = requests.get(url, headers=_api_headers(), timeout=15.0, verify=_api_verify_ssl())
        if res.status_code == 404:
            return {"found": False, "error": "media_not_found"}
        if res.status_code != 200:
            return {"found": False, "error": f"media_api_http_{res.status_code}"}
        body = res.json() if res.content else {}
        playlists = body.get("playlists") or []
        return {
            "found": True,
            "media_id": str(body.get("id") or media_id),
            "path": body.get("path") or body.get("formatted_path"),
            "title": body.get("title") or body.get("text"),
            "artist": body.get("artist"),
            "length": body.get("length"),
            "playlists": playlists,
            "in_playlist": bool(playlists),
        }
    except Exception as exc:
        logger.warning("get_media_file_info failed: %s", exc)
        return {"found": False, "error": exc.__class__.__name__}


def get_playlist_info(playlist_id: str, *, station_id: str | None = None) -> dict:
    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    url = f"{base_url}/api/station/{station_id}/playlist/{playlist_id}"
    try:
        res = requests.get(url, headers=_api_headers(), timeout=15.0, verify=_api_verify_ssl())
        if res.status_code != 200:
            return {"found": False, "error": f"playlist_http_{res.status_code}"}
        body = res.json()
        return {
            "found": True,
            "playlist_id": str(playlist_id),
            "name": body.get("name"),
            "is_enabled": body.get("is_enabled"),
            "type": body.get("type"),
            "source": body.get("source"),
            "include_in_requests": body.get("include_in_requests"),
            "num_songs": body.get("num_songs"),
        }
    except Exception as exc:
        return {"found": False, "error": exc.__class__.__name__}


def append_media_to_playlist(
    media_id: str,
    *,
    playlist_id: str | None = None,
    file_path: str | None = None,
    station_id: str | None = None,
) -> dict:
    """Append media to playlist when API supports order/append."""
    if not azuracast_writes_enabled():
        return _writes_hard_block("playlist append")

    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    playlist_id = playlist_id or _get_playlist_id()
    if not playlist_id:
        return {"success": False, "error": "playlist_id_missing", "capability_missing": True}

    headers = {**_api_headers(), "Content-Type": "application/json"}
    order_url = f"{base_url}/api/station/{station_id}/playlist/{playlist_id}/order"
    try:
        order_payload = {"order": [int(media_id)]} if str(media_id).isdigit() else {"order": [media_id]}
        res = requests.put(order_url, headers=headers, json=order_payload, timeout=30.0, verify=_api_verify_ssl())
        if res.status_code in (200, 201, 204):
            return {"success": True, "playlist_id": playlist_id, "method": "order_put"}
        append_url = f"{base_url}/api/station/{station_id}/playlist/{playlist_id}/append"
        payload = {"id": media_id}
        if file_path:
            payload["path"] = file_path
        res2 = requests.post(append_url, headers=headers, json=payload, timeout=30.0, verify=_api_verify_ssl())
        if res2.status_code in (200, 201, 204):
            return {"success": True, "playlist_id": playlist_id, "method": "append_post"}
        return {
            "success": False,
            "error": f"playlist_assign_http_{res.status_code}",
            "detail": (res.text or res2.text or "")[:200],
            "capability_missing": res.status_code == 405 and res2.status_code == 405,
        }
    except Exception as exc:
        return {"success": False, "error": exc.__class__.__name__}


def queue_media_files_batch(
    file_paths: list[str],
    *,
    do: str = "queue",
    station_id: str | None = None,
) -> dict:
    """Queue or play media via PUT /api/station/{id}/files/batch (do=queue|immediate)."""
    if not azuracast_writes_enabled():
        return _writes_hard_block("queueing")

    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    if not _is_configured(base_url) or not _is_configured(_get_api_key()):
        return {"success": False, "capability_missing": True, "error": "azuracast_config_missing"}

    if do not in ("queue", "immediate"):
        do = "queue"
    normalized = [p.strip().lstrip("/") for p in file_paths if p]
    if not normalized:
        return {"success": False, "error": "no_file_paths"}

    url = f"{base_url}/api/station/{station_id}/files/batch"
    headers = {**_api_headers(), "Content-Type": "application/json"}
    try:
        res = requests.put(
            url,
            headers=headers,
            json={"do": do, "files": normalized},
            timeout=45.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code not in (200, 201):
            return {
                "success": False,
                "error": f"batch_http_{res.status_code}",
                "detail": (res.text or "")[:200],
                "capability_missing": res.status_code == 405,
            }
        body = res.json() if res.content else {}
        errors = body.get("errors") or []
        return {
            "success": bool(body.get("success", True)) and not errors,
            "do": do,
            "files": body.get("files") or normalized,
            "errors": errors,
        }
    except Exception as exc:
        return {"success": False, "error": exc.__class__.__name__}


def get_station_playback_snapshot(*, station_id: str | None = None) -> dict:
    """Queue length + station playback hints (read-only)."""
    base_url = _get_base_url().rstrip("/")
    station_id = station_id or _get_station_id()
    snapshot: dict = {"queue_length": 0, "requests_enabled": None, "playlists_enabled": 0}

    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}/queue",
            headers=_api_headers(),
            timeout=12.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code == 200:
            q = res.json()
            if isinstance(q, list):
                snapshot["queue_length"] = len(q)
    except Exception:
        pass

    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}/playlists",
            headers=_api_headers(),
            timeout=12.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code == 200:
            playlists = res.json()
            if isinstance(playlists, list):
                snapshot["playlists_enabled"] = sum(
                    1 for p in playlists if isinstance(p, dict) and p.get("is_enabled")
                )
    except Exception:
        pass

    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}",
            headers=_api_headers(),
            timeout=12.0,
            verify=_api_verify_ssl(),
        )
        if res.status_code == 200:
            st = res.json()
            snapshot["enable_requests"] = st.get("enable_requests")
            snapshot["requests_enabled"] = st.get("enable_requests")
            snapshot["backend"] = st.get("backend")
    except Exception:
        pass

    return snapshot


def get_station_schedule_truth(*, station_id: str | None = None, rows: int = 20) -> dict:
    """
    AzuraCast-backed schedule/playlist/queue/next truth for Neena tools.
    Never invents timed dayparts; empty timed schedule is honest empty.
    """
    base_url = (_get_base_url() or "").rstrip("/")
    station_id = station_id or _get_station_id()
    out: dict = {
        "checked": False,
        "source": "azuracast",
        "managed_target": "azuracast",
        "neena_role": "separate_agent_product",
        "timed_slots": [],
        "timed_schedule_available": False,
        "timed_schedule_status": "unchecked",
        "playlists": [],
        "queue_length": 0,
        "queue_peek": [],
        "playing_next": None,
        "next_status": "unchecked",
        "errors": [],
    }
    if not _is_configured(base_url):
        out["timed_schedule_status"] = "azura_unavailable"
        out["next_status"] = "azura_unavailable"
        out["errors"].append("AZURACAST_BASE_URL missing")
        return out

    headers = _api_headers()
    verify = _api_verify_ssl()

    # Timed schedule (may be empty on stations without clock schedules)
    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}/schedule",
            headers=headers,
            params={"rows": max(1, min(int(rows or 20), 50))},
            timeout=12.0,
            verify=verify,
        )
        if res.status_code == 200:
            raw = res.json()
            slots = raw if isinstance(raw, list) else (raw.get("rows") or raw.get("schedule") or [])
            if not isinstance(slots, list):
                slots = []
            cleaned = []
            for item in slots[:30]:
                if not isinstance(item, dict):
                    continue
                cleaned.append(
                    {
                        "id": item.get("id"),
                        "type": item.get("type") or item.get("schedule_items_type"),
                        "start_time": item.get("start_time") or item.get("start_timestamp"),
                        "end_time": item.get("end_time") or item.get("end_timestamp"),
                        "start_date": item.get("start_date"),
                        "end_date": item.get("end_date"),
                        "days": item.get("days") or item.get("play_once_date"),
                        "playlist_id": item.get("playlist_id")
                        or (item.get("playlist") or {}).get("id"),
                        "playlist_name": item.get("name")
                        or (item.get("playlist") or {}).get("name"),
                    }
                )
            out["timed_slots"] = cleaned
            out["timed_schedule_available"] = bool(cleaned)
            out["timed_schedule_status"] = "ok" if cleaned else "empty"
            out["checked"] = True
        else:
            out["timed_schedule_status"] = f"http_{res.status_code}"
            out["errors"].append(f"schedule_http_{res.status_code}")
    except Exception as exc:
        out["timed_schedule_status"] = "error"
        out["errors"].append(f"schedule:{type(exc).__name__}")

    # Playlists inventory
    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}/playlists",
            headers=headers,
            timeout=12.0,
            verify=verify,
        )
        if res.status_code == 200:
            playlists = res.json()
            if isinstance(playlists, list):
                out["playlists"] = [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "is_enabled": bool(p.get("is_enabled")),
                        "type": p.get("type"),
                        "order": p.get("order"),
                    }
                    for p in playlists[:40]
                    if isinstance(p, dict)
                ]
                out["checked"] = True
        else:
            out["errors"].append(f"playlists_http_{res.status_code}")
    except Exception as exc:
        out["errors"].append(f"playlists:{type(exc).__name__}")

    # Queue peek
    try:
        res = requests.get(
            f"{base_url}/api/station/{station_id}/queue",
            headers=headers,
            timeout=12.0,
            verify=verify,
        )
        if res.status_code == 200:
            q = res.json()
            if isinstance(q, list):
                out["queue_length"] = len(q)
                peek = []
                for item in q[:5]:
                    if not isinstance(item, dict):
                        continue
                    song = item.get("song") if isinstance(item.get("song"), dict) else {}
                    peek.append(
                        {
                            "title": song.get("title") or item.get("title"),
                            "artist": song.get("artist") or item.get("artist"),
                            "sent_to_autodj": item.get("sent_to_autodj"),
                        }
                    )
                out["queue_peek"] = peek
                out["checked"] = True
        else:
            out["errors"].append(f"queue_http_{res.status_code}")
    except Exception as exc:
        out["errors"].append(f"queue:{type(exc).__name__}")

    # playing_next from public nowplaying
    try:
        res = requests.get(
            f"{base_url}/api/nowplaying/{station_id}",
            timeout=8.0,
            verify=verify,
        )
        if res.status_code == 200:
            data = res.json()
            if not isinstance(data, dict):
                data = {}
            nxt = data.get("playing_next")
            if isinstance(nxt, dict):
                song = nxt.get("song") if isinstance(nxt.get("song"), dict) else {}
                title = song.get("title") or nxt.get("title")
                artist = song.get("artist") or nxt.get("artist")
                if title:
                    out["playing_next"] = {
                        "title": title,
                        "artist": artist,
                        "cued_at": nxt.get("cued_at"),
                        "duration": nxt.get("duration"),
                    }
                    out["next_status"] = "ok"
                else:
                    out["next_status"] = "next_unavailable"
            else:
                out["next_status"] = "next_unavailable"
            out["checked"] = True
        else:
            out["next_status"] = f"http_{res.status_code}"
    except Exception as exc:
        out["next_status"] = "error"
        out["errors"].append(f"nowplaying:{type(exc).__name__}")

    if not out["checked"] and out["errors"]:
        out["timed_schedule_status"] = out.get("timed_schedule_status") or "azura_unavailable"
    return out


def send_capsule_to_azuracast_api(
    capsule_id: int,
    audio_file_path: str,
    *,
    title: str | None = None,
) -> dict:
    """
    Real AzuraCast API push for an already-gated approved capsule with real audio.
    Caller must validate capsule gates before invoking.
    """
    config = check_azuracast_write_config()
    push_mode = config.get("mode")

    if push_mode == "local_simulated" or _get_push_mode() == "local_simulated":
        from services.broadcast.playout import push_capsule_local_simulated

        playlist_name = _get_playlist_id() or _get_target_folder() or "default"
        sim = push_capsule_local_simulated(audio_file_path, playlist_name)
        return {
            "success": sim.get("success", False),
            "mode": "local_simulated",
            "azuracast_status": "simulated" if sim.get("success") else "failed",
            "message": sim.get("message", ""),
            "error_message": None if sim.get("success") else sim.get("message"),
            "media_id": None,
            "playlist_id": playlist_name,
            "truth_level": "simulated",
        }

    if not azuracast_writes_enabled() or push_mode == "writes_disabled":
        blocked = _writes_hard_block("upload")
        return {
            "success": False,
            "mode": "blocked",
            "azuracast_status": "blocked",
            "message": blocked["error"],
            "error_message": blocked["error"],
            "writes_enabled": False,
        }

    if push_mode == "blocked":
        missing = ", ".join(config.get("missing") or [])
        return {
            "success": False,
            "mode": "blocked",
            "azuracast_status": "blocked",
            "message": f"AzuraCast blocked: missing config ({missing})",
            "error_message": f"AzuraCast blocked: missing config ({missing})",
        }

    upload = upload_media_file(
        audio_file_path,
        target_folder=_get_target_folder() or None,
    )
    if not upload.get("success"):
        return {
            "success": False,
            "mode": "failed",
            "azuracast_status": "failed",
            "message": upload.get("error", "Upload failed"),
            "error_message": upload.get("error"),
        }

    media_id = upload.get("media_id")
    assign = assign_media_to_playlist_or_folder(
        media_id or "",
        file_path=upload.get("response_summary", {}).get("path"),
    )
    if not assign.get("success"):
        return {
            "success": False,
            "mode": "failed",
            "azuracast_status": "failed",
            "media_id": media_id,
            "message": assign.get("error", "Playlist assignment failed"),
            "error_message": assign.get("error"),
            "upload_summary": upload.get("response_summary"),
        }

    az_status = "scheduled" if assign.get("scheduled") else "uploaded"
    folder = _get_target_folder()
    strategy = assign.get("target_strategy") or ("playlist" if assign.get("scheduled") else "folder" if folder else "upload_only")
    upload_summary = dict(upload.get("response_summary") or {})
    upload_summary["target_strategy"] = strategy
    if folder and strategy == "folder":
        upload_summary["target_folder"] = folder
    return {
        "success": True,
        "mode": "real_api",
        "azuracast_status": az_status,
        "media_id": media_id,
        "playlist_id": assign.get("playlist_id") or _get_playlist_id() or None,
        "target_strategy": strategy,
        "target_folder": folder if strategy == "folder" else None,
        "message": (
            f"AzuraCast {az_status}: media uploaded"
            + (" and appended to playlist." if assign.get("scheduled") else (
                f" to folder {folder}." if folder else " to station media."
            ))
        ),
        "error_message": None,
        "upload_summary": upload_summary,
        "truth_level": "real",
    }

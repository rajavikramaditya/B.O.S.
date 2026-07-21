"""Listener-path diagnose + remote app_config switch (frozen app stays untouched).

Single responsibility: probe station/stream vs public app URLs and update
allowlisted app_config keys so the mobile app can be fixed without rebuild.
"""
from __future__ import annotations

import logging
import os
import socket
from typing import Any
from urllib.parse import urlparse

import requests

import database as db

logger = logging.getLogger(__name__)

APP_CONFIG_ALLOWLIST = frozenset(
    {
        "api_base_url",
        "stream_url",
        "backup_stream_url",
        "maintenance_mode",
        "maintenance_message",
        "force_update",
        "force_refresh",
        "minimum_supported_version",
        "min_app_version",
        "config_version",
    }
)

KNOWN_GOOD_STREAM_URL = "http://35.244.15.150/listen/orai_radio/radio.mp3"
KNOWN_GOOD_API_BASE = "http://35.244.15.150:8080"
# Frozen app baked-in defaults (orai-radio-station/src/lib/appConfig.ts)
FROZEN_APP_DEFAULT_API = "https://api.orairadio.in"
FROZEN_APP_DEFAULT_STREAM = "https://stream.orairadio.in/listen/orai_radio/radio.mp3"


def _hostname(url: str) -> str | None:
    try:
        host = (urlparse(url).hostname or "").strip()
        return host or None
    except Exception:
        return None


def _dns_ok(host: str | None) -> dict[str, Any]:
    if not host:
        return {"ok": False, "host": None, "error": "missing_host", "ips": []}
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({item[4][0] for item in infos if item and item[4]})
        return {"ok": bool(ips), "host": host, "ips": ips, "error": None}
    except Exception as exc:
        return {"ok": False, "host": host, "ips": [], "error": type(exc).__name__}


def _http_probe(url: str, *, stream: bool = False, timeout: float = 6.0) -> dict[str, Any]:
    if not (url or "").strip():
        return {"ok": False, "url": url or "", "error": "empty_url", "http_status": None}
    try:
        if stream:
            with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as res:
                chunk = next(res.iter_content(chunk_size=256), b"")
                ok = res.status_code < 400 and bool(chunk)
                return {
                    "ok": ok,
                    "url": url,
                    "http_status": res.status_code,
                    "bytes_sample": len(chunk or b""),
                    "error": None if ok else "no_audio_bytes",
                }
        res = requests.get(url, timeout=timeout, allow_redirects=True)
        ok = res.status_code < 400
        return {
            "ok": ok,
            "url": url,
            "http_status": res.status_code,
            "bytes_sample": len(res.content or b""),
            "error": None if ok else f"http_{res.status_code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "http_status": None,
            "bytes_sample": 0,
            "error": type(exc).__name__,
        }


def get_app_listener_config() -> dict[str, Any]:
    cfg = db.get_app_config() or {}
    return {
        "api_base_url": cfg.get("api_base_url") or os.environ.get("APP_API_BASE_URL") or KNOWN_GOOD_API_BASE,
        "stream_url": cfg.get("stream_url") or os.environ.get("STREAM_PUBLIC_URL") or KNOWN_GOOD_STREAM_URL,
        "backup_stream_url": cfg.get("backup_stream_url") or "",
        "maintenance_mode": bool(cfg.get("maintenance_mode", False)),
        "raw_keys": sorted(k for k in cfg.keys() if k in APP_CONFIG_ALLOWLIST),
    }


def set_app_listener_config(
    *,
    stream_url: str | None = None,
    api_base_url: str | None = None,
    backup_stream_url: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Update allowlisted listener URLs. Requires confirmed=True (owner one-tap)."""
    if not confirmed:
        return {
            "success": False,
            "blocked": True,
            "require_confirmation": True,
            "message": "App stream/API URL badalne se pehle owner confirm chahiye.",
        }

    updates: dict[str, str] = {}
    if stream_url is not None:
        updates["stream_url"] = str(stream_url).strip()
    if api_base_url is not None:
        updates["api_base_url"] = str(api_base_url).strip().rstrip("/")
    if backup_stream_url is not None:
        updates["backup_stream_url"] = str(backup_stream_url).strip()

    if not updates:
        return {"success": False, "blocked": True, "message": "Koi allowlisted URL field nahi diya."}

    for key, value in updates.items():
        if key not in APP_CONFIG_ALLOWLIST:
            return {"success": False, "blocked": True, "message": f"Key '{key}' allowlist me nahi."}
        if key.endswith("_url") and value and not value.startswith(("http://", "https://")):
            return {"success": False, "blocked": True, "message": f"{key} valid http(s) URL hona chahiye."}
        db.update_app_config(key, value)

    return {
        "success": True,
        "blocked": False,
        "updated": updates,
        "config": get_app_listener_config(),
        "message": "App remote config update ho gaya. App force-close karke dubara open karo.",
    }


def propose_known_good_fix() -> dict[str, str]:
    return {
        "stream_url": os.environ.get("STREAM_PUBLIC_URL") or KNOWN_GOOD_STREAM_URL,
        "api_base_url": (os.environ.get("APP_API_BASE_URL") or KNOWN_GOOD_API_BASE).rstrip("/"),
        "backup_stream_url": KNOWN_GOOD_STREAM_URL,
    }


def diagnose_listener_path() -> dict[str, Any]:
    """Real probes — never invent online/offline."""
    cfg = get_app_listener_config()
    stream_url = cfg.get("stream_url") or ""
    api_base = (cfg.get("api_base_url") or "").rstrip("/")
    backup = cfg.get("backup_stream_url") or ""

    station: dict[str, Any] = {"checked": False}
    try:
        from services.broadcast.azuracast_client import get_azuracast_status

        az = get_azuracast_status() or {}
        station = {
            "checked": True,
            "configured": bool(az.get("configured")),
            "stream_reachable": bool(az.get("stream_reachable")),
            "icecast_status": az.get("icecast_status"),
            "now_playing_title": az.get("now_playing_title"),
            "listeners": az.get("listener_count"),
            "station_stream_url": az.get("stream_url"),
        }
    except Exception as exc:
        station = {"checked": True, "error": type(exc).__name__}

    icecast_url = station.get("station_stream_url") or os.environ.get("AZURACAST_STREAM_URL") or KNOWN_GOOD_STREAM_URL
    if icecast_url in ("(not set)", "", None):
        icecast_url = KNOWN_GOOD_STREAM_URL

    icecast_probe = _http_probe(str(icecast_url), stream=True)
    app_stream_dns = _dns_ok(_hostname(stream_url))
    app_stream_probe = _http_probe(stream_url, stream=True) if app_stream_dns.get("ok") else {
        "ok": False,
        "url": stream_url,
        "http_status": None,
        "error": "dns_failed",
        "bytes_sample": 0,
    }
    backup_dns = _dns_ok(_hostname(backup)) if backup else {"ok": False, "host": None, "error": "empty"}
    backup_probe = (
        _http_probe(backup, stream=True)
        if backup and backup_dns.get("ok")
        else {"ok": False, "url": backup, "error": "skipped_or_dns", "http_status": None}
    )
    api_dns = _dns_ok(_hostname(api_base))
    api_cfg_url = f"{api_base}/api/public/app-config" if api_base else ""
    api_probe = _http_probe(api_cfg_url) if api_dns.get("ok") and api_cfg_url else {
        "ok": False,
        "url": api_cfg_url,
        "error": "dns_failed",
        "http_status": None,
    }
    # Docker/VM hairpin: public IP:8080 often fails from inside the container
    # even when the API is healthy on localhost.
    if not api_probe.get("ok"):
        local_api = _http_probe("http://127.0.0.1:8080/api/public/app-config")
        if local_api.get("ok"):
            api_probe = {
                **local_api,
                "url": api_cfg_url or local_api.get("url"),
                "note": "public_ip_hairpin_failed_localhost_ok",
            }

    # Frozen app always tries these domains first (hardcoded). Probe them even
    # when DB app_config already has IP URLs — otherwise diagnose lies "healthy".
    frozen_api_dns = _dns_ok(_hostname(FROZEN_APP_DEFAULT_API))
    frozen_stream_dns = _dns_ok(_hostname(FROZEN_APP_DEFAULT_STREAM))
    frozen_api_probe = (
        _http_probe(f"{FROZEN_APP_DEFAULT_API}/api/public/app-config")
        if frozen_api_dns.get("ok")
        else {"ok": False, "url": f"{FROZEN_APP_DEFAULT_API}/api/public/app-config", "error": "dns_failed"}
    )
    frozen_stream_probe = (
        _http_probe(FROZEN_APP_DEFAULT_STREAM, stream=True)
        if frozen_stream_dns.get("ok")
        else {"ok": False, "url": FROZEN_APP_DEFAULT_STREAM, "error": "dns_failed"}
    )
    frozen_app_ok = bool(frozen_api_probe.get("ok") and frozen_stream_probe.get("ok"))

    station_ok = bool(icecast_probe.get("ok") or station.get("stream_reachable"))
    app_urls_ok = bool(app_stream_probe.get("ok") and api_probe.get("ok"))

    if station_ok and frozen_app_ok and app_urls_ok:
        verdict = "healthy"
        next_step = "Listener path theek dikh raha hai. App force-close karke play try karo."
    elif not station_ok:
        verdict = "station_offline"
        next_step = "Pehle AzuraCast/Icecast theek karo (Overview On the Air + listen URL)."
    elif station_ok and not frozen_app_ok:
        verdict = "station_ok_app_url_dead"
        next_step = (
            "Station chal raha hai, lekin frozen app ke default domains "
            "(api.orairadio.in / stream.orairadio.in) DNS/HTTPS fail. "
            "Owner: A-record → 35.244.15.150 (+ SSL for https). "
            "DB app_config IP URLs tabhi kaam aate hain jab app API fetch kar paaye."
        )
    elif station_ok and (not app_stream_dns.get("ok") or not api_dns.get("ok")):
        verdict = "station_ok_app_url_dead"
        next_step = (
            "Station chal raha hai, lekin app_config URLs DNS fail. "
            "Confirm ke baad known-good IP URLs set kar sakti hoon."
        )
    elif station_ok and not app_stream_probe.get("ok"):
        verdict = "config_ok_stream_down"
        next_step = "API/DNS theek, lekin app stream_url se audio bytes nahi aa rahe — URL/SSL check karo."
    else:
        verdict = "station_ok_app_url_dead"
        next_step = "App primary URL fail; known-good IP config propose kar sakti hoon (confirm chahiye)."

    proposed = propose_known_good_fix() if verdict != "healthy" else None

    return {
        "tool_name": "diagnose_listener_path",
        "verdict": verdict,
        "next_step": next_step,
        "station": station,
        "icecast_probe": icecast_probe,
        "app_config": {
            "api_base_url": api_base,
            "stream_url": stream_url,
            "backup_stream_url": backup,
        },
        "app_stream_dns": app_stream_dns,
        "app_stream_probe": app_stream_probe,
        "backup_stream_dns": backup_dns,
        "backup_stream_probe": backup_probe,
        "api_dns": api_dns,
        "api_config_probe": api_probe,
        "frozen_app_defaults": {
            "api_base": FROZEN_APP_DEFAULT_API,
            "stream_url": FROZEN_APP_DEFAULT_STREAM,
            "api_dns": frozen_api_dns,
            "stream_dns": frozen_stream_dns,
            "api_probe": frozen_api_probe,
            "stream_probe": frozen_stream_probe,
        },
        "proposed_fix": proposed,
        "message": f"Verdict: {verdict}. {next_step}",
    }


def format_diagnose_reply(diag: dict[str, Any]) -> str:
    v = diag.get("verdict")
    station = diag.get("station") or {}
    lines = [
        f"Listener-path check: **{v}**.",
        f"Station/Icecast: {'OK' if (diag.get('icecast_probe') or {}).get('ok') else 'FAIL'} "
        f"(now playing: {station.get('now_playing_title') or 'n/a'}).",
        f"App stream URL DNS: {'OK' if (diag.get('app_stream_dns') or {}).get('ok') else 'FAIL'} "
        f"| probe: {'OK' if (diag.get('app_stream_probe') or {}).get('ok') else 'FAIL'}.",
        f"App API config DNS: {'OK' if (diag.get('api_dns') or {}).get('ok') else 'FAIL'} "
        f"| probe: {'OK' if (diag.get('api_config_probe') or {}).get('ok') else 'FAIL'}.",
    ]
    frozen = diag.get("frozen_app_defaults") or {}
    if frozen:
        lines.append(
            "Frozen app defaults: "
            f"api.orairadio.in DNS={'OK' if (frozen.get('api_dns') or {}).get('ok') else 'FAIL'} "
            f"| stream.orairadio.in DNS={'OK' if (frozen.get('stream_dns') or {}).get('ok') else 'FAIL'}."
        )
    lines.append(diag.get("next_step") or "")
    prop = diag.get("proposed_fix")
    if prop and v != "healthy":
        lines.append(
            "Main known-good IP URLs set kar sakti hoon (app rebuild nahi)."
        )
        lines.append(f"Propose: stream={prop.get('stream_url')} api={prop.get('api_base_url')}")
        lines.append(
            "Note: frozen app pehle api.orairadio.in se config maangti hai — "
            "DNS theek hone tak domain fallback fail rahega; DNS owner side pe fix karna hoga."
        )
    return "\n".join(x for x in lines if x)


__all__ = [
    "APP_CONFIG_ALLOWLIST",
    "diagnose_listener_path",
    "format_diagnose_reply",
    "get_app_listener_config",
    "propose_known_good_fix",
    "set_app_listener_config",
]

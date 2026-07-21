"""
M4-A7 — Cached cockpit stream probe (keeps fast_health responsive).
"""
from __future__ import annotations

import threading
import time
from typing import Any

_STREAM_CACHE: dict[str, Any] = {"at": 0.0, "online": False, "error": None}
_STREAM_CACHE_TTL = 15.0
_REFRESH_INFLIGHT = False


def peek_stream_online_cached() -> tuple[bool | None, bool]:
    """Return cached stream state only. (online|None, from_cache). Never probes AzuraCast."""
    now = time.time()
    cached_at = float(_STREAM_CACHE.get("at") or 0.0)
    if cached_at and (now - cached_at) < _STREAM_CACHE_TTL:
        return bool(_STREAM_CACHE.get("online")), True
    return None, False


def get_stream_online_cached() -> tuple[bool, bool]:
    """Return (stream_online, from_cache)."""
    now = time.time()
    cached_at = float(_STREAM_CACHE.get("at") or 0.0)
    if cached_at and (now - cached_at) < _STREAM_CACHE_TTL:
        return bool(_STREAM_CACHE.get("online")), True

    online = False
    err: str | None = None
    try:
        from services.broadcast.stream_verification import (
            check_stream_url,
            get_now_playing_snapshot,
        )

        # Primary truth for "is radio streaming": Icecast/mount HTTP 200/206.
        # Now-playing metadata can 404 when AZURACAST_BASE_URL points at admin
        # proxy instead of AzuraCast — that must not mark a live mount as offline.
        mount = check_stream_url()
        if mount.get("stream_reachable"):
            online = True
        else:
            np = get_now_playing_snapshot()
            online = bool(
                np.get("checked") and not np.get("error") and np.get("station_online", True)
            )
            err = np.get("error") or mount.get("error")
        if not online and err is None:
            err = mount.get("error")
        _STREAM_CACHE["error"] = err
    except Exception as exc:
        _STREAM_CACHE["error"] = type(exc).__name__

    _STREAM_CACHE["at"] = now
    _STREAM_CACHE["online"] = online
    return online, False


def trigger_stream_cache_refresh_background() -> None:
    """Non-blocking AzuraCast probe to refresh stream cache (never blocks HTTP poll)."""
    global _REFRESH_INFLIGHT
    if _REFRESH_INFLIGHT:
        return

    def _run() -> None:
        global _REFRESH_INFLIGHT
        try:
            get_stream_online_cached()
        finally:
            _REFRESH_INFLIGHT = False

    _REFRESH_INFLIGHT = True
    threading.Thread(target=_run, daemon=True, name="stream_cache_refresh").start()


__all__ = [
    "get_stream_online_cached",
    "peek_stream_online_cached",
    "trigger_stream_cache_refresh_background",
]

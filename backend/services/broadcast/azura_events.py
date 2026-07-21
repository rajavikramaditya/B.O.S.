"""AzuraCast webhook events — fast path for stream/media truth (no poll theatre)."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_KEY = "neena:live:azura_events"
_PENDING_KEY = "neena:live:azura_verify_pending"
_MAX_EVENTS = 40
_FALLBACK_EVENTS: list[dict[str, Any]] = []
_FALLBACK_PENDING: dict[str, Any] = {}


def webhook_secret() -> str:
    return (os.environ.get("AZURACAST_WEBHOOK_SECRET") or os.environ.get("NEENA_AZURA_WEBHOOK_SECRET") or "").strip()


def record_event(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize and store an inbound Azura webhook payload."""
    body = payload if isinstance(payload, dict) else {}
    event_type = (
        str(body.get("type") or body.get("event") or body.get("webhook_type") or "unknown")
        .strip()
        .lower()
    )
    now_playing = body.get("now_playing") if isinstance(body.get("now_playing"), dict) else {}
    song = now_playing.get("song") if isinstance(now_playing.get("song"), dict) else {}
    if not song and isinstance(body.get("song"), dict):
        song = body["song"]
    entry = {
        "ts": time.time(),
        "type": event_type,
        "title": str(song.get("title") or body.get("title") or "")[:200],
        "artist": str(song.get("artist") or body.get("artist") or "")[:200],
        "station": str(body.get("station") or body.get("station_id") or "")[:80],
        "raw_keys": sorted(list(body.keys()))[:30],
    }
    events = list(_FALLBACK_EVENTS)
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            raw = client.get(_KEY)
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, list):
                    events = loaded
    except Exception as exc:
        logger.debug("azura_events load: %s", exc)
    events.insert(0, entry)
    events = events[:_MAX_EVENTS]
    _FALLBACK_EVENTS.clear()
    _FALLBACK_EVENTS.extend(events)
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            client.setex(_KEY, 6 * 3600, json.dumps(events, ensure_ascii=False, default=str))
    except Exception as exc:
        logger.debug("azura_events save: %s", exc)
    # Clear pending verify waiters on song/media-ish events
    if any(x in event_type for x in ("song", "now", "media", "live", "stream", "unknown")):
        clear_pending_verify(reason="webhook_event")
    return entry


def latest_events(limit: int = 5) -> list[dict[str, Any]]:
    events = list(_FALLBACK_EVENTS)
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            raw = client.get(_KEY)
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, list):
                    events = loaded
    except Exception:
        pass
    return events[: max(1, min(limit, 20))]


def mark_pending_verify(*, capsule_id: int | None = None, action: str = "verify") -> None:
    pending = {
        "ts": time.time(),
        "capsule_id": capsule_id,
        "action": action,
        "status": "waiting_webhook",
    }
    _FALLBACK_PENDING.clear()
    _FALLBACK_PENDING.update(pending)
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            client.setex(_PENDING_KEY, 600, json.dumps(pending, default=str))
    except Exception:
        pass


def clear_pending_verify(*, reason: str = "") -> dict[str, Any] | None:
    prev = dict(_FALLBACK_PENDING) if _FALLBACK_PENDING else None
    _FALLBACK_PENDING.clear()
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            raw = client.get(_PENDING_KEY)
            if raw and not prev:
                try:
                    prev = json.loads(raw)
                except Exception:
                    prev = {"raw": True}
            client.delete(_PENDING_KEY)
    except Exception:
        pass
    if prev:
        prev["cleared_reason"] = reason
    return prev


def wait_for_webhook_or_oneshot(
    *,
    capsule_id: int | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Fast path: short wait for webhook; then one-shot nowplaying. No 60s poll loop."""
    start = time.time()
    mark_pending_verify(capsule_id=capsule_id, action="verify")
    deadline = start + max(0.5, min(float(timeout_seconds), 15.0))
    got_event = None
    while time.time() < deadline:
        events = latest_events(3)
        if events and float(events[0].get("ts") or 0) >= start - 0.05:
            got_event = events[0]
            break
        time.sleep(0.35)
    oneshot: dict[str, Any] = {}
    try:
        from services.broadcast.azuracast_client import get_azuracast_status

        oneshot = get_azuracast_status() or {}
    except Exception as exc:
        oneshot = {"error": str(exc)[:160]}
    clear_pending_verify(reason="wait_done")
    return {
        "webhook_event": got_event,
        "oneshot": {
            "now_playing_title": oneshot.get("now_playing_title"),
            "now_playing_artist": oneshot.get("now_playing_artist"),
            "stream_reachable": oneshot.get("stream_reachable"),
        },
        "path": "webhook_then_oneshot" if got_event else "oneshot_only",
    }


__all__ = [
    "clear_pending_verify",
    "latest_events",
    "mark_pending_verify",
    "record_event",
    "wait_for_webhook_or_oneshot",
    "webhook_secret",
]

"""M4-A8.2-B / M4-A8.3 — Shared fast cockpit-status snapshot (no Gemini, probe optional)."""
from __future__ import annotations

from typing import Any

import services.cockpit.runtime_controller as rc
from services.cockpit.health_cache import (
    peek_stream_online_cached,
    trigger_stream_cache_refresh_background,
)
from services.cockpit.launch_health import get_memory_stack_summary_fast
from services.llm.provider_router import peek_cooldown_wait


def _owner_wants_concise() -> bool:
    """Owner's persisted 'keep it short' preference (best-effort; never blocks)."""
    try:
        import services.brain.manager_state as manager_state

        return manager_state.is_concise_mode()
    except Exception:
        return False


def get_cockpit_status_snapshot(
    *,
    allow_stream_probe: bool = False,
    capsule_limit: int = 20,
    include_capsules: bool = True,
) -> dict[str, Any]:
    """
    Build cockpit-status shape. Default is cache-only (never hits AzuraCast on poll).
    """
    from services.broadcast.capsule_service import list_recent_capsules
    from services.voice.gen_service import get_broadcast_audio_readiness

    cooldown_wait = peek_cooldown_wait("gemini-3.1-flash-lite")
    launch = {
        "backend": "online",
        "brain_status": "cooldown" if cooldown_wait > 0 else "ready",
    }

    memory_summary = get_memory_stack_summary_fast()
    readiness = get_broadcast_audio_readiness()

    capsules: list[dict[str, Any]] = []
    last_verified = None
    if include_capsules:
        capsules = list_recent_capsules(limit=max(1, int(capsule_limit)))
        last_verified = next(
            (
                c.get("id")
                for c in capsules
                if c.get("stream_verification_status") == "verified"
            ),
            None,
        )
    else:
        recent = list_recent_capsules(limit=5)
        last_verified = next(
            (
                c.get("id")
                for c in recent
                if c.get("stream_verification_status") == "verified"
            ),
            None,
        )

    stream_stale = False
    if allow_stream_probe:
        from services.cockpit.health_cache import get_stream_online_cached

        stream_online, stream_cached = get_stream_online_cached()
    else:
        stream_online, stream_cached = peek_stream_online_cached()
        if stream_online is None:
            stream_stale = True

    stats = rc.get_system_stats()
    wa = rc.peek_whatsapp_gateway_trace_status()

    return {
        "health_tier": "fast_health",
        "launch": launch,
        "broadcast_readiness": readiness,
        "capsules": capsules,
        "last_verified_capsule_id": last_verified,
        "stream_online": stream_online,
        "stream_status_cached": stream_cached,
        "stream_stale": stream_stale,
        "memory_stack_summary": memory_summary,
        "degraded_due_to_memory_stack_offline": memory_summary.get(
            "degraded_due_to_memory_stack_offline"
        ),
        "whatsapp_gateway": wa,
        "local_stats": stats,
    }


def get_cockpit_status_snapshot_immediate() -> dict[str, Any]:
    """Ultra-light snapshot for immediate cockpit actions (<2s target)."""
    return get_cockpit_status_snapshot(
        allow_stream_probe=False,
        capsule_limit=3,
        include_capsules=False,
    )


def get_cockpit_status_ui_snapshot() -> dict[str, Any]:
    """GET /api/neena/cockpit-status — cache-only poll with optional background refresh."""
    snapshot = get_cockpit_status_snapshot(
        allow_stream_probe=False,
        capsule_limit=5,
        include_capsules=True,
    )
    if snapshot.get("stream_stale"):
        trigger_stream_cache_refresh_background()
    return snapshot


def format_station_status_message(snapshot: dict[str, Any]) -> str:
    """Short owner-facing status from cached cockpit snapshot."""
    launch = snapshot.get("launch") or {}
    mem = snapshot.get("memory_stack_summary") or {}
    readiness = snapshot.get("broadcast_readiness") or {}
    stream_on = snapshot.get("stream_online")
    stream_cached = snapshot.get("stream_status_cached")
    stream_stale = snapshot.get("stream_stale")
    verified = snapshot.get("last_verified_capsule_id")
    stats = snapshot.get("local_stats") or {}
    brain = launch.get("brain_status") or "ready"
    wa = snapshot.get("whatsapp_gateway") or "unknown"

    if stream_on is True:
        stream_line = "Stream: online"
    elif stream_on is False:
        stream_line = "Stream: offline/unreachable"
    else:
        stream_line = "Stream: checking… (background refresh)"

    if stream_cached and stream_on is not None:
        stream_line += " [cached]"
    if stream_stale:
        stream_line += " — pehla poll cache miss; thodi der me update"

    pg = mem.get("postgres") or ("healthy" if mem.get("postgres_available") else "unknown")
    redis_st = mem.get("redis") or ("healthy" if mem.get("redis_available") else "unknown")
    tts = readiness.get("tts_status") or "unknown"
    can_audio = readiness.get("can_produce_real_audio")

    # Concise preference: owner asked to keep replies short — one-line summary.
    if _owner_wants_concise():
        stream_short = "online" if stream_on is True else ("offline" if stream_on is False else "unknown")
        return (
            f"Station status. brain={brain} stream={stream_short} "
            f"cpu={stats.get('cpu', '?')} ram={stats.get('ram', '?')}."
        )

    lines = [
        "Station status.",
        f"- Brain: {brain} | Backend: online",
        f"- {stream_line}",
        f"- Memory stack: PG={pg}, Redis={redis_st}",
        f"- TTS/broadcast: {tts}, real_audio={'yes' if can_audio else 'no'}",
        f"- WhatsApp: {wa} (non-blocking)",
        f"- CPU {stats.get('cpu', '?')}%, RAM {stats.get('ram', '?')}%",
    ]
    if verified:
        lines.append(f"- Last verified capsule: #{verified}")
    return "\n".join(lines)


def format_diagnostics_fast_message(snapshot: dict[str, Any]) -> str:
    """Fast diagnostics from cached cockpit data only."""
    mem = snapshot.get("memory_stack_summary") or {}
    stream_on = snapshot.get("stream_online")
    stream_cached = snapshot.get("stream_status_cached")
    stream_stale = snapshot.get("stream_stale")
    stats = snapshot.get("local_stats") or {}
    wa = snapshot.get("whatsapp_gateway") or "unknown"
    degraded = snapshot.get("degraded_due_to_memory_stack_offline")

    issues = []
    if degraded:
        issues.append("memory_stack_degraded")
    if stream_on is False:
        issues.append("stream_offline")
    if stream_stale:
        # Informational — not a station failure; background refresh already triggered.
        issues.append("stream_cache_warming")
    if wa == "offline":
        issues.append("whatsapp_offline_non_blocking")

    stream_txt = (
        "online"
        if stream_on is True
        else ("offline" if stream_on is False else "checking")
    )
    if stream_cached and stream_on is not None:
        stream_txt += " (cached)"
    if stream_stale:
        stream_txt += " (warming)"

    cpu = float(stats.get("cpu") or 0)
    ram = float(stats.get("ram") or 0)
    overload = ""
    if cpu > 85 or ram > 85:
        overload = (
            f"System load high hai: CPU {cpu:.0f}%, RAM {ram:.0f}%. "
            "Heavy creative commands slow ho sakte hain; status/diagnostics local chal sakte hain. "
        )

    # Concise preference: short one-line diagnostics unless there are issues to show.
    if _owner_wants_concise():
        if issues:
            return overload + f"Diagnostics: {len(issues)} issue(s) — {', '.join(issues)}."
        return overload + f"Diagnostics: sab clear. Stream {stream_txt}, CPU {cpu:.0f}%/RAM {ram:.0f}%."

    lines = [
        overload + "Fast diagnostics (cached checks, no deep probe):",
        f"- Backend: active",
        f"- Stream: {stream_txt}",
        f"- Memory stack: PG={mem.get('postgres', 'unknown')}, Redis={mem.get('redis', 'unknown')}",
        f"- WhatsApp gateway: {wa}",
        f"- Local CPU: {stats.get('cpu', 0)}%, RAM: {stats.get('ram', 0)}%",
        f"- Issues flagged: {len(issues)} ({', '.join(issues) if issues else 'none'})",
    ]
    return "\n".join(lines)


__all__ = [
    "format_diagnostics_fast_message",
    "format_station_status_message",
    "get_cockpit_status_snapshot",
    "get_cockpit_status_snapshot_immediate",
    "get_cockpit_status_ui_snapshot",
]

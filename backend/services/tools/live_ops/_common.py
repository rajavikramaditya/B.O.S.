"""Shared helpers for live-ops hands (ADR-013 Wave 2)."""
from __future__ import annotations

from typing import Any


def registry_entry(snapshot: dict, action_id: str) -> dict | None:
    for entry in snapshot.get("action_registry") or []:
        if entry.get("action_id") == action_id:
            return entry
    return None


def pending_capsules(snapshot: dict) -> list[dict]:
    return [
        c
        for c in (snapshot.get("latest_capsules") or [])
        if (c.get("approval_status") or "") in ("pending", "pending_review")
        or (c.get("status") or "") in ("pending_approval",)
    ]


def listener_diag_packet(diag: dict[str, Any], *, owner_must_confirm: bool = False) -> dict[str, Any]:
    station = diag.get("station") or {}
    icecast = diag.get("icecast_probe") or {}
    return {
        "tool": "diagnose_listener_path",
        "status": "needs_confirmation" if owner_must_confirm else (diag.get("verdict") or "unknown"),
        "owner_must_confirm": owner_must_confirm,
        "verdict": diag.get("verdict"),
        "next_step": diag.get("next_step"),
        "facts": [
            f"icecast_ok={bool(icecast.get('ok'))}",
            f"now_playing={station.get('now_playing_title') or 'n/a'}",
            f"app_stream_dns_ok={bool((diag.get('app_stream_dns') or {}).get('ok'))}",
            f"app_stream_probe_ok={bool((diag.get('app_stream_probe') or {}).get('ok'))}",
            f"api_dns_ok={bool((diag.get('api_dns') or {}).get('ok'))}",
            f"api_config_probe_ok={bool((diag.get('api_config_probe') or {}).get('ok'))}",
        ],
        "proposed_fix": diag.get("proposed_fix"),
        "message": diag.get("message"),
    }

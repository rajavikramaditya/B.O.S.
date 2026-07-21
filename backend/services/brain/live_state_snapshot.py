"""M4-A8.4 — NEENA_LIVE_STATE_SNAPSHOT builder (live control + state awareness)."""
from __future__ import annotations

from typing import Any

import database as db
from services.safety.admin_security import security_status
from services.cockpit.action_registry import build_action_registry, registry_to_public_map
from services.cockpit.status_fast import get_cockpit_status_snapshot


def _norm_stream(stream_online: bool | None, stream_stale: bool) -> str:
    if stream_stale or stream_online is None:
        return "unknown"
    return "online" if stream_online else "offline"


def _norm_tts(readiness: dict) -> str:
    audio = readiness.get("audio") or {}
    if audio.get("can_produce_real_audio"):
        return "real"
    if audio.get("can_produce_simulated_audio") or audio.get("simulated_available"):
        return "simulated"
    return "not_ready"


def _norm_azuracast(readiness: dict) -> str:
    az = readiness.get("azuracast") or {}
    return "ready" if az.get("ready_for_real_push") else "not_ready"


def _list_active_jobs(limit: int = 5) -> list[dict]:
    try:
        from services.cockpit.job_service import list_active_jobs

        return list_active_jobs(limit=limit)
    except Exception:
        return []


def _pending_scripts(limit: int = 10) -> list[dict]:
    try:
        rows = db.get_pending_approvals(limit=limit)
        return [dict(r) for r in rows]
    except Exception:
        return []


def _pick_latest_pending_capsule(capsules: list[dict]) -> dict | None:
    for c in capsules:
        if c.get("approval_status") in ("pending", "pending_review"):
            return c
    return None


def _pick_latest_approved_needs_audio(capsules: list[dict]) -> dict | None:
    for c in capsules:
        if c.get("approval_status") == "approved" and (c.get("audio_truth_level") or "none") == "none":
            return c
    return None


def _pick_latest_ready_azuracast(capsules: list[dict]) -> dict | None:
    for c in capsules:
        if c.get("azuracast_push_allowed"):
            return c
    return None


def _compute_recommended_next_action(
    *,
    pending_count: int,
    latest_pending: dict | None,
    latest_approved_no_audio: dict | None,
    latest_ready_azura: dict | None,
    stream: str,
) -> str:
    if latest_pending:
        cid = latest_pending.get("id")
        return f"approve_capsule_{cid}"
    if latest_approved_no_audio:
        cid = latest_approved_no_audio.get("id")
        return f"generate_audio_capsule_{cid}"
    if latest_ready_azura:
        cid = latest_ready_azura.get("id")
        return f"send_azuracast_capsule_{cid}"
    if stream in ("offline", "unknown"):
        return "verify_stream"
    if pending_count == 0:
        return "create_rj_intro_or_station_status"
    return "review_neena_lab"


def build_neena_live_state_snapshot(*, include_deep_health: bool = False) -> dict[str, Any]:
    """
    Aggregate live Command Center state from caches/DB (no blocking probes unless deep).
    """
    cockpit = get_cockpit_status_snapshot(
        allow_stream_probe=False,
        capsule_limit=10,
        include_capsules=True,
    )
    sec = security_status()
    auth_required = bool(sec.get("auth_required"))
    launch = cockpit.get("launch") or {}
    readiness = cockpit.get("broadcast_readiness") or {}
    capsules = cockpit.get("capsules") or []
    pending_scripts = _pending_scripts()
    latest_pending = _pick_latest_pending_capsule(capsules)
    latest_approved_no_audio = _pick_latest_approved_needs_audio(capsules)
    latest_ready_azura = _pick_latest_ready_azuracast(capsules)
    stream = _norm_stream(cockpit.get("stream_online"), bool(cockpit.get("stream_stale")))
    wa = cockpit.get("whatsapp_gateway") or "unknown"
    local_stats = cockpit.get("local_stats") or {}
    cpu = float(local_stats.get("cpu") or 0)
    ram = float(local_stats.get("ram") or 0)
    resource_warning = None
    if cpu > 85 or ram > 85:
        resource_warning = (
            f"System load high hai: CPU {cpu:.0f}%, RAM {ram:.0f}%. "
            "Main heavy creative commands slow kar sakti hoon, lekin status/diagnostics local mode me chala sakti hoon."
        )

    snapshot: dict[str, Any] = {
        "server": launch.get("backend") or "online",
        "auth": "locked" if auth_required else "unlocked",
        "brain": launch.get("brain_status") or "ready",
        "tts": _norm_tts(readiness),
        "azuracast": _norm_azuracast(readiness),
        "stream": stream,
        "whatsapp": wa if wa in ("online", "offline") else "non_blocking",
        "pending_scripts_count": len(pending_scripts),
        "pending_scripts": [
            {
                "id": p.get("id"),
                "asset_type": p.get("asset_type"),
                "status": p.get("status"),
                "preview": (p.get("content_data") or "")[:120],
            }
            for p in pending_scripts
        ],
        "latest_capsules": [
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "capsule_type": c.get("capsule_type"),
                "approval_status": c.get("approval_status"),
                "approval_queue_id": c.get("approval_queue_id"),
                "audio_truth_level": c.get("audio_truth_level"),
                "azuracast_status": c.get("azuracast_status"),
                "stream_verification_status": c.get("stream_verification_status"),
                "azuracast_push_allowed": c.get("azuracast_push_allowed"),
                "azuracast_push_block_reason": c.get("azuracast_push_block_reason"),
            }
            for c in capsules[:5]
        ],
        "latest_pending_capsule": latest_pending,
        "latest_approved_needs_audio": latest_approved_no_audio,
        "latest_ready_for_azuracast": latest_ready_azura,
        "active_jobs": _list_active_jobs(),
        "stream_status_cached": cockpit.get("stream_status_cached"),
        "stream_stale": cockpit.get("stream_stale"),
        "last_verified_capsule_id": cockpit.get("last_verified_capsule_id"),
        "memory_stack_summary": cockpit.get("memory_stack_summary"),
        "broadcast_blockers": readiness.get("blockers") or [],
        "local_stats": {"cpu": cpu, "ram": ram},
        "resource_warning": resource_warning,
    }

    snapshot["recommended_next_action"] = _compute_recommended_next_action(
        pending_count=snapshot["pending_scripts_count"],
        latest_pending=latest_pending,
        latest_approved_no_audio=latest_approved_no_audio,
        latest_ready_azura=latest_ready_azura,
        stream=stream,
    )

    registry = build_action_registry(snapshot)
    reg_map = registry_to_public_map(registry)
    snapshot["available_actions"] = reg_map["available_actions"]
    snapshot["blocked_actions"] = reg_map["blocked_actions"]
    snapshot["action_registry"] = reg_map["actions"]

    if include_deep_health:
        try:
            from services.cockpit.launch_health import get_deep_launch_health

            snapshot["deep_health"] = get_deep_launch_health()
        except Exception as exc:
            snapshot["deep_health"] = {"error": str(exc)[:200]}

    return snapshot


def format_snapshot_for_interpreter(snapshot: dict[str, Any]) -> str:
    """Compact live state for command interpreter context (no secrets)."""
    lines = [
        f"server={snapshot.get('server')} auth={snapshot.get('auth')} brain={snapshot.get('brain')}",
        f"tts={snapshot.get('tts')} azuracast={snapshot.get('azuracast')} stream={snapshot.get('stream')}",
        f"pending_scripts_count={snapshot.get('pending_scripts_count')} recommended_next={snapshot.get('recommended_next_action')}",
    ]
    for c in (snapshot.get("latest_capsules") or [])[:3]:
        lines.append(
            f"capsule #{c.get('id')} type={c.get('capsule_type')} approval={c.get('approval_status')} "
            f"audio={c.get('audio_truth_level')} azura={c.get('azuracast_status')} stream_verify={c.get('stream_verification_status')}"
        )
    if snapshot.get("active_jobs"):
        for j in snapshot["active_jobs"][:2]:
            lines.append(f"active_job {j.get('job_id')} action={j.get('action')} status={j.get('status')}")
    enabled = snapshot.get("available_actions") or []
    lines.append(f"available_actions={','.join(enabled[:12])}")
    return "\n".join(lines)


def build_live_recommendation_reply(snapshot: dict[str, Any]) -> str:
    """Short factual next-step line from live snapshot (humanize owns Hinglish)."""
    prefix = ""
    rw = snapshot.get("resource_warning")
    if rw:
        prefix = rw + " "

    pending = snapshot.get("pending_scripts_count") or 0
    latest = snapshot.get("latest_pending_capsule")
    rec = snapshot.get("recommended_next_action") or ""

    if latest and rec.startswith("approve_capsule_"):
        cid = latest.get("id")
        title = latest.get("title") or latest.get("capsule_type") or "script"
        return prefix + f"{pending} pending. Latest Capsule #{cid} ({title}) needs review/approve."

    cap = snapshot.get("latest_approved_needs_audio")
    if cap and rec.startswith("generate_audio"):
        return prefix + f"Capsule #{cap.get('id')} approved. Next: generate audio."

    cap = snapshot.get("latest_ready_for_azuracast")
    if cap and rec.startswith("send_azuracast"):
        return prefix + f"Capsule #{cap.get('id')} audio ready. Next: AzuraCast upload."

    for c in snapshot.get("latest_capsules") or []:
        az = c.get("azuracast_status") or ""
        sv = c.get("stream_verification_status") or ""
        if az in ("uploaded", "scheduled") and sv != "verified":
            return prefix + f"Capsule #{c.get('id')} uploaded. Next: verify stream."

    if rec == "verify_stream":
        stream = snapshot.get("stream")
        return prefix + f"Stream shows {stream}. Run Verify Stream."

    if pending == 0:
        stream = snapshot.get("stream") or "unknown"
        if stream == "online":
            return prefix + "System online. You can create a new RJ intro or ad script."
        return prefix + "No pending scripts. Create RJ/ad script, or check Status/Diagnostics."

    return prefix + f"{pending} pending item(s). Review in Neena Lab, or open/approve latest script."


__all__ = [
    "build_live_recommendation_reply",
    "build_neena_live_state_snapshot",
    "format_snapshot_for_interpreter",
]

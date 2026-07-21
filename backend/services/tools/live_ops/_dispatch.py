"""Internal live-ops dispatch body (ADR-013 W2). Category modules call run_action."""

from __future__ import annotations

import logging
from typing import Any

from services.broadcast.approval_queue import process_approval_action
from services.cockpit.action_service import dispatch_cockpit_action, execute_cockpit_action_for_chat
from services.brain.factual_reply import build_live_ops_result
from services.brain.live_state_snapshot import build_neena_live_state_snapshot
from services.tools.live_ops._common import (
    listener_diag_packet as _listener_diag_packet,
    pending_capsules as _pending_capsules,
)

logger = logging.getLogger(__name__)


def _handle_approve_capsule(
    snap: dict,
    target_id: int | None,
    slots: dict,
    owner_message: str = "",
) -> dict:
    from services.broadcast.capsule_service import get_capsule_by_id
    from services.broadcast.approval_queue import process_approval_action

    if target_id:
        capsule = get_capsule_by_id(target_id)
    else:
        pending_caps = _pending_capsules(snap)
        capsule = snap.get("latest_pending_capsule") or (pending_caps[0] if len(pending_caps) == 1 else None)
        if len(pending_caps) > 1 and not capsule:
            ids = [c.get("id") for c in pending_caps[:5]]
            return build_live_ops_result(
                "APPROVE_MULTIPLE",
                packet={
                    "tool": "approve_capsule",
                    "status": "needs_selection",
                    "owner_must_confirm": True,
                    "pending_ids": ids,
                    "next_step": "specify_capsule_id",
                },
                fallback_line=f"Multiple pending scripts ({', '.join(f'#{i}' for i in ids)}). Specify which capsule to approve.",
                blocked=True,
                ok=False,
                require_confirmation=True,
            )

    if not capsule:
        return build_live_ops_result(
            "APPROVE_NONE",
            packet={"tool": "approve_capsule", "status": "none", "next_step": "create_or_wait_for_script"},
            fallback_line="No pending script to approve.",
            blocked=True,
            ok=False,
        )

    cid = capsule.get("id")
    status = capsule.get("status") or "draft"
    if status == "approved":
        return build_live_ops_result(
            "APPROVE_ALREADY_DONE",
            packet={
                "tool": "approve_capsule",
                "status": "already_approved",
                "capsule_id": cid,
                "next_step": "generate_audio",
            },
            fallback_line=f"Capsule #{cid} already approved. Next step: generate audio.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    aid = capsule.get("approval_queue_id")
    if aid is None:
        return build_live_ops_result(
            "APPROVE_BLOCKED",
            packet={
                "tool": "approve_capsule",
                "status": "blocked",
                "capsule_id": cid,
                "reason": "approval_queue_link_missing",
            },
            fallback_line=f"Capsule #{cid} pending but approval queue link missing.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    try:
        process_approval_action(int(aid), "approve")
    except Exception as exc:
        logger.warning("Legacy queue approval skipped or failed: %s", exc)

    from services.broadcast.capsule_review import mark_capsule_script_approved
    res = mark_capsule_script_approved(cid)
    if res and res.get("status") == "approved":
        return build_live_ops_result(
            "APPROVE_CAPSULE",
            packet={
                "tool": "approve_capsule",
                "status": "ok",
                "capsule_id": cid,
                "approval_id": int(aid),
                "next_step": "generate_audio",
            },
            fallback_line=f"Capsule #{cid} approved. Next step: generate audio.",
            ok=True,
            blocked=False,
            approval_id=int(aid),
            capsule_id=cid,
            ui_action={"type": "refresh_cockpit"},
        )

    return build_live_ops_result(
        "APPROVE_FAILED",
        packet={"tool": "approve_capsule", "status": "failed", "capsule_id": cid},
        fallback_line=f"Capsule #{cid} approve failed.",
        blocked=True,
        ok=False,
    )


def _handle_reject_capsule(
    snap: dict,
    target_id: int | None,
    reason: str,
    rejected_by: str = "owner",
) -> dict:
    from services.broadcast.capsule_service import get_capsule_by_id
    from services.broadcast.approval_queue import process_approval_action

    if target_id:
        capsule = get_capsule_by_id(target_id)
    else:
        pending_caps = _pending_capsules(snap)
        capsule = snap.get("latest_pending_capsule") or (pending_caps[0] if len(pending_caps) == 1 else None)
        if len(pending_caps) > 1 and not capsule:
            ids = [c.get("id") for c in pending_caps[:5]]
            return build_live_ops_result(
                "REJECT_MULTIPLE",
                packet={
                    "tool": "reject_capsule",
                    "status": "needs_selection",
                    "owner_must_confirm": True,
                    "pending_ids": ids,
                },
                fallback_line=f"Multiple pending scripts ({', '.join(f'#{i}' for i in ids)}). Specify which to reject.",
                blocked=True,
                ok=False,
                require_confirmation=True,
            )

    if not capsule:
        return build_live_ops_result(
            "REJECT_NONE",
            packet={"tool": "reject_capsule", "status": "none"},
            fallback_line="No pending script to reject.",
            blocked=True,
            ok=False,
        )

    cid = capsule.get("id")
    status = capsule.get("status") or "draft"
    if status == "rejected":
        return build_live_ops_result(
            "REJECT_ALREADY_DONE",
            packet={"tool": "reject_capsule", "status": "already_rejected", "capsule_id": cid},
            fallback_line=f"Capsule #{cid} already rejected.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    aid = capsule.get("approval_queue_id")
    if aid is None:
        return build_live_ops_result(
            "REJECT_BLOCKED",
            packet={
                "tool": "reject_capsule",
                "status": "blocked",
                "capsule_id": cid,
                "reason": "approval_queue_link_missing",
            },
            fallback_line=f"Capsule #{cid} pending but approval queue link missing.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    try:
        process_approval_action(int(aid), "reject")
    except Exception as exc:
        logger.warning("Legacy queue rejection skipped or failed: %s", exc)

    from services.broadcast.capsule_review import mark_capsule_script_rejected
    res = mark_capsule_script_rejected(cid, reason=reason)
    if res and res.get("status") == "rejected":
        return build_live_ops_result(
            "REJECT_CAPSULE",
            packet={
                "tool": "reject_capsule",
                "status": "ok",
                "capsule_id": cid,
                "reason": reason,
                "approval_id": int(aid),
            },
            fallback_line=f"Capsule #{cid} rejected. Reason: {reason}.",
            ok=True,
            blocked=False,
            approval_id=int(aid),
            capsule_id=cid,
            ui_action={"type": "refresh_cockpit"},
        )

    return build_live_ops_result(
        "REJECT_FAILED",
        packet={"tool": "reject_capsule", "status": "failed", "capsule_id": cid},
        fallback_line=f"Capsule #{cid} reject failed.",
        blocked=True,
        ok=False,
    )


def _handle_needs_revision(
    snap: dict,
    target_id: int | None,
    reason: str | None = None,
) -> dict:
    from services.broadcast.capsule_review import mark_capsule_needs_revision
    from services.broadcast.capsule_service import get_capsule_by_id

    if target_id:
        capsule = get_capsule_by_id(target_id)
    else:
        pending_caps = _pending_capsules(snap)
        capsule = snap.get("latest_pending_capsule") or (pending_caps[0] if len(pending_caps) == 1 else None)
        if len(pending_caps) > 1 and not capsule:
            ids = [c.get("id") for c in pending_caps[:5]]
            return build_live_ops_result(
                "REVISION_MULTIPLE",
                packet={
                    "tool": "needs_revision",
                    "status": "needs_selection",
                    "owner_must_confirm": True,
                    "pending_ids": ids,
                },
                fallback_line=f"Multiple pending scripts ({', '.join(f'#{i}' for i in ids)}). Specify which needs revision.",
                blocked=True,
                ok=False,
                require_confirmation=True,
            )

    if not capsule:
        return build_live_ops_result(
            "REVISION_NONE",
            packet={"tool": "needs_revision", "status": "none"},
            fallback_line="No pending script for revision.",
            blocked=True,
            ok=False,
        )

    cid = capsule.get("id")
    status = capsule.get("status") or "draft"
    if status == "needs_revision":
        return build_live_ops_result(
            "REVISION_ALREADY_DONE",
            packet={"tool": "needs_revision", "status": "already_needs_revision", "capsule_id": cid},
            fallback_line=f"Capsule #{cid} already marked needs_revision.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    res = mark_capsule_needs_revision(cid, reason=reason)
    if res and res.get("status") == "needs_revision":
        return build_live_ops_result(
            "NEEDS_REVISION",
            packet={
                "tool": "needs_revision",
                "status": "ok",
                "capsule_id": cid,
                "reason": reason,
            },
            fallback_line=f"Capsule #{cid} marked needs_revision.",
            ok=True,
            blocked=False,
            capsule_id=cid,
            ui_action={"type": "refresh_cockpit"},
        )

    return build_live_ops_result(
        "REVISION_FAILED",
        packet={"tool": "needs_revision", "status": "failed", "capsule_id": cid},
        fallback_line=f"Capsule #{cid} revision mark failed.",
        blocked=True,
        ok=False,
    )


def _handle_prepare_audio(
    snap: dict,
    target_id: int | None,
) -> dict:
    from services.broadcast.capsule_service import get_capsule_by_id
    from services.voice.gen_service import generate_capsule_audio

    if target_id:
        capsule = get_capsule_by_id(target_id)
    else:
        capsule = snap.get("latest_approved_needs_audio")
        if not capsule:
            pending_caps = _pending_capsules(snap)
            capsule = snap.get("latest_pending_capsule") or (pending_caps[0] if len(pending_caps) == 1 else None)

    if not capsule:
        return build_live_ops_result(
            "GENERATE_AUDIO_BLOCKED",
            packet={
                "tool": "generate_audio",
                "status": "blocked",
                "reason": "no_approved_script",
                "next_step": "approve_script_first",
            },
            fallback_line="Audio blocked: approve a script first.",
        )

    cid = int(capsule.get("id"))
    status = capsule.get("status") or "draft"
    if status not in ("approved", "audio_pending"):
        return build_live_ops_result(
            "GENERATE_AUDIO_BLOCKED",
            packet={
                "tool": "generate_audio",
                "status": "blocked",
                "capsule_id": cid,
                "capsule_state": status,
                "reason": "script_not_approved",
            },
            fallback_line=f"Audio blocked for Capsule #{cid}: state is {status}; approve first.",
        )

    result = generate_capsule_audio(cid, regenerate=True)
    if result.get("success"):
        truth_level = result.get("audio_truth_level")
        return build_live_ops_result(
            "GENERATE_AUDIO",
            packet={
                "tool": "generate_audio",
                "status": "ok",
                "capsule_id": cid,
                "audio_truth_level": truth_level,
            },
            fallback_line=(
                f"Simulated audio generated for Capsule #{cid} (preview only)."
                if truth_level == "simulated"
                else f"Real TTS audio generated for Capsule #{cid}."
            ),
            capsule_id=cid,
            success=True,
            ui_action={"type": "refresh_cockpit"},
        )

    return build_live_ops_result(
        "GENERATE_AUDIO_FAILED",
        packet={
            "tool": "generate_audio",
            "status": "failed",
            "capsule_id": cid,
            "message": result.get("message"),
        },
        fallback_line=result.get("message") or "Audio generation failed.",
    )


def _handle_approve_latest_script(
    snap: dict,
    slots: dict,
    owner_message: str = "",
) -> dict:
    """Safe approve-latest workflow — never raises; no HTTP 500 for normal states."""
    pending_caps = _pending_capsules(snap)
    latest_pending = snap.get("latest_pending_capsule") or (pending_caps[0] if len(pending_caps) == 1 else None)
    latest_approved = snap.get("latest_approved_needs_audio")
    latest_capsule = ((snap.get("latest_capsules") or [None])[0])

    if len(pending_caps) > 1:
        ids = [c.get("id") for c in pending_caps[:5]]
        return build_live_ops_result(
            "APPROVE_MULTIPLE",
            packet={
                "tool": "approve_latest_script",
                "status": "needs_selection",
                "owner_must_confirm": True,
                "pending_ids": ids,
            },
            fallback_line=f"Multiple pending scripts ({', '.join(f'#{i}' for i in ids)}). Specify which to approve.",
            blocked=True,
            ok=False,
            require_confirmation=True,
        )

    if not latest_pending:
        if latest_approved:
            cid = latest_approved.get("id")
            return build_live_ops_result(
                "APPROVE_ALREADY_DONE",
                packet={
                    "tool": "approve_latest_script",
                    "status": "already_approved",
                    "capsule_id": cid,
                    "next_step": "generate_audio",
                },
                fallback_line=f"Capsule #{cid} already approved. Next step: generate audio.",
                blocked=True,
                ok=False,
                capsule_id=cid,
                approval_id=latest_approved.get("approval_queue_id"),
            )
        if latest_capsule and latest_capsule.get("approval_status") == "approved":
            cid = latest_capsule.get("id")
            return build_live_ops_result(
                "APPROVE_ALREADY_DONE",
                packet={
                    "tool": "approve_latest_script",
                    "status": "already_approved",
                    "capsule_id": cid,
                    "next_step": "generate_audio",
                },
                fallback_line=f"Capsule #{cid} already approved. Next step: generate audio.",
                blocked=True,
                ok=False,
                capsule_id=cid,
            )
        return build_live_ops_result(
            "APPROVE_NONE",
            packet={"tool": "approve_latest_script", "status": "none"},
            fallback_line="No pending script to approve.",
            blocked=True,
            ok=False,
        )

    explicit = bool(slots.get("explicit_approval")) or any(
        w in (owner_message or "").lower()
        for w in ("approve karo", "approve kar do", "approve kar", "approve latest", "approve kro")
    )
    if not explicit and slots.get("needs_confirmation", True):
        cid = latest_pending.get("id")
        return build_live_ops_result(
            "APPROVE_CONFIRM",
            packet={
                "tool": "approve_latest_script",
                "status": "needs_confirmation",
                "owner_must_confirm": True,
                "capsule_id": cid,
                "next_step": "reply_haan_or_nahi",
            },
            fallback_line=f"Confirm required: approve Capsule #{cid}. Reply haan or nahi.",
            require_confirmation=True,
            capsule_id=cid,
            approval_id=latest_pending.get("approval_queue_id"),
            ok=True,
        )

    aid_raw = latest_pending.get("approval_queue_id")
    if aid_raw is None:
        cid = latest_pending.get("id")
        return build_live_ops_result(
            "APPROVE_BLOCKED",
            packet={
                "tool": "approve_latest_script",
                "status": "blocked",
                "capsule_id": cid,
                "reason": "approval_queue_link_missing",
            },
            fallback_line=f"Capsule #{cid} pending but approval queue link missing. Review in Neena Lab.",
            blocked=True,
            ok=False,
            capsule_id=cid,
        )

    try:
        aid = int(aid_raw)
    except (TypeError, ValueError):
        return build_live_ops_result(
            "APPROVE_BLOCKED",
            packet={"tool": "approve_latest_script", "status": "blocked", "reason": "invalid_approval_id"},
            fallback_line="Approval ID invalid — check pending script in Neena Lab.",
            blocked=True,
            ok=False,
        )

    try:
        res = process_approval_action(aid, "approve")
    except Exception as exc:
        logger.error("approve_latest failed: %s", type(exc).__name__)
        return build_live_ops_result(
            "APPROVE_FAILED",
            packet={
                "tool": "approve_latest_script",
                "status": "failed",
                "error_type": type(exc).__name__,
            },
            fallback_line=f"Approve failed ({type(exc).__name__}). Retry shortly.",
            blocked=True,
            ok=False,
        )

    cid = latest_pending.get("id")
    if res.get("success"):
        return build_live_ops_result(
            "APPROVE_LATEST",
            packet={
                "tool": "approve_latest_script",
                "status": "ok",
                "capsule_id": cid,
                "approval_id": aid,
                "next_step": "generate_audio",
            },
            fallback_line=f"Capsule #{cid} approved. Next step: generate audio.",
            ok=True,
            blocked=False,
            approval_id=aid,
            capsule_id=cid,
            ui_action={"type": "refresh_cockpit"},
        )

    msg = (res.get("message") or "unknown error").lower()
    if "already" in msg or "approved" in msg:
        return build_live_ops_result(
            "APPROVE_ALREADY_DONE",
            packet={
                "tool": "approve_latest_script",
                "status": "already_approved",
                "capsule_id": cid,
                "approval_id": aid,
                "next_step": "generate_audio",
            },
            fallback_line=f"Capsule #{cid} already approved. Next step: generate audio.",
            blocked=True,
            ok=False,
            capsule_id=cid,
            approval_id=aid,
        )

    return build_live_ops_result(
        "APPROVE_FAILED",
        packet={
            "tool": "approve_latest_script",
            "status": "failed",
            "message": res.get("message", "unknown error"),
        },
        fallback_line=f"Approve failed: {res.get('message', 'unknown error')}",
        blocked=True,
        ok=False,
    )


def _capabilities_packet(snapshot: dict) -> tuple[dict[str, Any], str, dict]:
    from services.brain.capability_manifest import build_capability_manifest
    from services.voice.gen_service import get_broadcast_audio_readiness

    manifest = build_capability_manifest()
    readiness = get_broadcast_audio_readiness()
    wa = (snapshot.get("whatsapp_gateway") or "unknown").lower()
    stream = snapshot.get("stream") or "unknown"
    stream_stale = bool(snapshot.get("stream_stale"))

    facts = [
        "safe_admin: capsule status, review approve/reject/revision, VM/diagnostics, stream verify, model/memory, script draft",
    ]
    if not readiness.get("real_push_ready"):
        facts.append("real_audio_azuracast_broadcast_blocked_without_owner_approval_and_config")
    if wa in {"offline", "unknown", "down", "error", "unavailable"}:
        facts.append("whatsapp_offline_or_non_blocking")
    if stream_stale or stream in {"unknown", "stale", None}:
        facts.append("stream_verify_required")

    packet = {
        "tool": "capabilities",
        "status": "ok",
        "facts": facts,
        "whatsapp_gateway": wa,
        "stream": stream,
        "real_push_ready": bool(readiness.get("real_push_ready")),
        "capabilities_count": manifest.get("total_capabilities", 0),
        "unavailable_count": manifest.get("unavailable_capabilities", 0),
    }
    fallback = (
        "Safe admin available: capsule status/review, diagnostics, stream verify, model/memory, script draft. "
        + ("Real AzuraCast push blocked without approval/config. " if not readiness.get("real_push_ready") else "")
        + ("WhatsApp offline. " if wa in {"offline", "unknown", "down", "error", "unavailable"} else "")
        + ("Stream verify required." if stream_stale or stream in {"unknown", "stale", None} else "")
    ).strip()
    meta = {
        "capabilities_count": manifest.get("total_capabilities", 0),
        "unavailable_count": manifest.get("unavailable_capabilities", 0),
        "manifest": manifest,
    }
    return packet, fallback, meta


def _timeout_diagnosis_packet(snapshot: dict) -> tuple[dict[str, Any], str]:
    from services.llm.model_status import build_neena_model_status

    st = build_neena_model_status()
    facts = [
        "timeouts_can_happen_when_model_or_creative_blocks_chat",
        "local_commands_target_under_2s",
        "heavy_creative_jobs_run_in_background",
    ]
    if st.get("cooldown_active"):
        facts.append(f"brain_cooldown_seconds={st.get('cooldown_remaining_seconds')}")
    rw = snapshot.get("resource_warning")
    if rw:
        facts.append(f"resource_warning={rw}")
    packet = {"tool": "timeout_diagnosis", "status": "ok", "facts": facts}
    fallback = (
        "Timeouts can happen when model/creative blocks chat. "
        "Local commands stay fast; heavy jobs run in background."
        + (f" Cooldown ~{st.get('cooldown_remaining_seconds')}s." if st.get("cooldown_active") else "")
    )
    return packet, fallback


def _pipeline_status_packet(snapshot: dict) -> tuple[dict[str, Any], str]:
    pending = snapshot.get("pending_scripts_count") or 0
    jobs = snapshot.get("active_jobs") or []
    rec = snapshot.get("recommended_next_action") or "none"
    packet = {
        "tool": "pipeline_status",
        "status": "ok",
        "pending_scripts_count": pending,
        "recommended_next_action": rec,
        "active_jobs_count": len(jobs),
    }
    fallback = f"Pipeline: {pending} pending script(s). Recommended next: {rec}."
    if jobs:
        fallback += f" Active background jobs: {len(jobs)}."
    return packet, fallback


def _explain_button_packet(snapshot: dict, slots: dict) -> tuple[dict[str, Any], str]:
    button = (slots.get("button_name") or slots.get("button_id") or "").strip().lower()
    latest = snapshot.get("latest_pending_capsule")

    if not button:
        return (
            {
                "tool": "explain_button",
                "status": "needs_button_name",
                "options": ["Approve", "Audio", "AzuraCast", "Verify Stream", "Status"],
            },
            "Which button: Approve, Audio, AzuraCast, Verify Stream, or Status?",
        )

    if "approve" in button:
        if latest:
            cid = latest.get("id")
            return (
                {
                    "tool": "explain_button",
                    "button": "approve",
                    "status": "ok",
                    "capsule_id": cid,
                    "facts": ["moves_script_to_next_pipeline_step", "pending_capsule_active"],
                },
                f"Approve sends the script to the next pipeline step. Capsule #{cid} is pending.",
            )
        return (
            {"tool": "explain_button", "button": "approve", "status": "ok", "facts": ["active_when_pending"]},
            "Approve is active when a script is pending approval.",
        )

    if "audio" in button:
        cap = snapshot.get("latest_approved_needs_audio") or latest
        if cap and cap.get("approval_status") == "approved":
            return (
                {
                    "tool": "explain_button",
                    "button": "audio",
                    "status": "ok",
                    "capsule_id": cap.get("id"),
                    "facts": ["generates_voice", "approval_done"],
                },
                f"Audio generates voice for Capsule #{cap.get('id')} (approved).",
            )
        return (
            {"tool": "explain_button", "button": "audio", "status": "ok", "facts": ["requires_approved_script"]},
            "Audio runs after the script is approved.",
        )

    if "azura" in button or "azuracast" in button:
        cap = snapshot.get("latest_ready_for_azuracast")
        if cap:
            return (
                {
                    "tool": "explain_button",
                    "button": "azuracast",
                    "status": "ok",
                    "capsule_id": cap.get("id"),
                    "facts": ["uploads_real_audio", "push_ready"],
                },
                f"AzuraCast uploads real audio. Capsule #{cap.get('id')} is push-ready.",
            )
        reason = (snapshot.get("latest_capsules") or [{}])[0].get("azuracast_push_block_reason")
        return (
            {
                "tool": "explain_button",
                "button": "azuracast",
                "status": "blocked",
                "reason": reason or "approval/audio pending",
            },
            f"AzuraCast blocked: {reason or 'approval/audio pending'}.",
        )

    if "verify" in button or "stream" in button:
        stream = snapshot.get("stream")
        return (
            {
                "tool": "explain_button",
                "button": "verify_stream",
                "status": "ok",
                "stream": stream,
                "facts": ["background_on_air_check"],
            },
            f"Verify Stream checks on-air status in background. Current stream: {stream}.",
        )

    if "status" in button:
        return (
            {
                "tool": "explain_button",
                "button": "status",
                "status": "ok",
                "facts": ["cached_station_health", "brain_tts_azuracast_stream"],
            },
            "Status shows cached station health (brain, TTS, AzuraCast, stream).",
        )

    return (
        {
            "tool": "explain_button",
            "status": "unknown_button",
            "options": ["Approve", "Audio", "AzuraCast", "Verify Stream", "Status"],
        },
        "Unknown button. Use Approve, Audio, AzuraCast, Verify Stream, or Status.",
    )


def _recommendation_packet(snapshot: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Factual recommendation packet; fallback stays short (no polished Sir template)."""
    # Reuse decision logic via canned builder then strip — better: mirror branches.
    rw = snapshot.get("resource_warning")
    pending = snapshot.get("pending_scripts_count") or 0
    latest = snapshot.get("latest_pending_capsule")
    rec = snapshot.get("recommended_next_action") or ""

    packet: dict[str, Any] = {
        "tool": "what_should_i_do_now",
        "status": "ok",
        "recommended_next_action": rec,
        "pending_scripts_count": pending,
        "resource_warning": rw,
    }
    prefix = (rw + " ") if rw else ""

    if latest and rec.startswith("approve_capsule_"):
        cid = latest.get("id")
        title = latest.get("title") or latest.get("capsule_type") or "script"
        packet.update({"capsule_id": cid, "title": title, "next_step": "open_and_approve"})
        return packet, prefix + f"{pending} pending. Latest Capsule #{cid} ({title}) needs review/approve."

    cap = snapshot.get("latest_approved_needs_audio")
    if cap and rec.startswith("generate_audio"):
        packet.update({"capsule_id": cap.get("id"), "next_step": "generate_audio"})
        return packet, prefix + f"Capsule #{cap.get('id')} approved. Next: generate audio."

    cap = snapshot.get("latest_ready_for_azuracast")
    if cap and rec.startswith("send_azuracast"):
        packet.update({"capsule_id": cap.get("id"), "next_step": "send_azuracast"})
        return packet, prefix + f"Capsule #{cap.get('id')} audio ready. Next: AzuraCast upload."

    for c in snapshot.get("latest_capsules") or []:
        az = c.get("azuracast_status") or ""
        sv = c.get("stream_verification_status") or ""
        if az in ("uploaded", "scheduled") and sv != "verified":
            packet.update({"capsule_id": c.get("id"), "next_step": "verify_stream"})
            return packet, prefix + f"Capsule #{c.get('id')} uploaded. Next: verify stream."

    if rec == "verify_stream":
        stream = snapshot.get("stream")
        packet.update({"stream": stream, "next_step": "verify_stream"})
        return packet, prefix + f"Stream shows {stream}. Run Verify Stream."

    if pending == 0:
        stream = snapshot.get("stream") or "unknown"
        packet.update({"stream": stream, "next_step": "create_script_or_check_status"})
        if stream == "online":
            return packet, prefix + "System online. You can create a new RJ intro or ad script."
        return packet, prefix + "No pending scripts. Create RJ/ad script, or check Status/Diagnostics."

    packet["next_step"] = "review_in_neena_lab_or_open_latest"
    return packet, prefix + f"{pending} pending item(s). Review in Neena Lab, or open/approve latest script."


def dispatch_impl(
    action: str,
    slots: dict | None,
    *,
    snapshot: dict | None = None,
    owner_message: str = "",
) -> dict | None:
    """
    Concrete live-ops implementations (called from catalog handlers).
    Prefer try_execute_live_ops / catalog.execute from call sites.
    """
    action = (action or "").strip().lower()
    slots = dict(slots or {})
    snap = snapshot or build_neena_live_state_snapshot()

    if action == "what_should_i_do_now":
        packet, fallback = _recommendation_packet(snap)
        return build_live_ops_result(
            "LIVE_RECOMMENDATION",
            packet=packet,
            fallback_line=fallback,
            live_snapshot={"recommended_next_action": snap.get("recommended_next_action")},
            voice_phase="success",
        )

    if action == "capabilities":
        packet, fallback, cap_meta = _capabilities_packet(snap)
        return build_live_ops_result(
            "CAPABILITIES",
            packet=packet,
            fallback_line=fallback,
            voice_phase="success",
            _capability_manifest_meta=cap_meta,
        )

    if action == "admin_lock":
        return build_live_ops_result(
            "ADMIN_LOCK",
            packet={
                "tool": "admin_lock",
                "status": "ok",
                "facts": ["command_center_locked", "owner_phrase_required_to_unlock"],
            },
            fallback_line="Command Center locked. Owner phrase required to unlock.",
            ui_action={"type": "admin_lock"},
        )

    if action == "auth_session_explain":
        return build_live_ops_result(
            "AUTH_SESSION_EXPLAIN",
            packet={
                "tool": "auth_session_explain",
                "status": "ok",
                "facts": [
                    "unlock_cookie_ttl_days=7",
                    "close_tab_does_not_lock",
                    "lock_via_button_or_command",
                ],
            },
            fallback_line=(
                "Unlock session cookie lasts 7 days. Closing the tab does not lock. "
                "Use Lock button or say 'command center lock karo'."
            ),
        )

    if action == "vm_status":
        from services.brain.vm_status import build_vm_status_reply

        return {
            "reply": build_vm_status_reply(snap),
            "action_type": "VM_STATUS",
            "gemini_calls": 0,
        }

    if action == "now_playing":
        from services.broadcast.azuracast_client import get_azuracast_status

        st = get_azuracast_status() or {}
        title = st.get("now_playing_title") or "Unknown"
        artist = st.get("now_playing_artist") or "Unknown"
        reachable = st.get("stream_reachable")
        packet = {
            "tool": "now_playing",
            "status": "ok" if title and str(title).lower() != "unknown" else "unknown",
            "now_playing_title": title,
            "now_playing_artist": artist,
            "stream_reachable": reachable,
            "managed_target": "azuracast",
            "neena_role": "separate_agent_product",
        }
        line = (
            f"Now playing (AzuraCast target): title={title}; artist={artist}; "
            f"stream_reachable={reachable}."
        )
        return build_live_ops_result(
            "NOW_PLAYING",
            packet=packet,
            fallback_line=line,
        )

    if action == "get_station_schedule":
        from services.broadcast.azuracast_client import get_station_schedule_truth

        truth = get_station_schedule_truth(rows=int(slots.get("rows") or 20))
        checked = bool(truth.get("checked"))
        playlists = truth.get("playlists") or []
        slots_t = truth.get("timed_slots") or []
        nxt = truth.get("playing_next")
        if not checked:
            packet = {
                "tool": "get_station_schedule",
                "status": "cannot",
                "reason": "azura_schedule_unavailable",
                "errors": truth.get("errors") or [],
                "managed_target": "azuracast",
                "neena_role": "separate_agent_product",
                "sqlite_grid_used": False,
            }
            return build_live_ops_result(
                "STATION_SCHEDULE_CANNOT",
                packet=packet,
                fallback_line=(
                    "Cannot: AzuraCast schedule/playlist truth unavailable. "
                    "Main fake SQLite 8AM grid nahi bolungi."
                ),
            )
        packet = {
            "tool": "get_station_schedule",
            "status": "ok",
            "timed_schedule_status": truth.get("timed_schedule_status"),
            "timed_schedule_available": bool(truth.get("timed_schedule_available")),
            "timed_slot_count": len(slots_t),
            "timed_slots": slots_t[:10],
            "playlist_count": len(playlists),
            "playlists": playlists[:15],
            "queue_length": truth.get("queue_length") or 0,
            "queue_peek": truth.get("queue_peek") or [],
            "playing_next": nxt,
            "next_status": truth.get("next_status"),
            "managed_target": "azuracast",
            "neena_role": "separate_agent_product",
            "sqlite_grid_used": False,
        }
        if not truth.get("timed_schedule_available"):
            packet["timed_note"] = "cannot_clock_schedule"
        pl_names = ", ".join(
            f"#{p.get('id')}:{p.get('name')}" for p in playlists[:8] if isinstance(p, dict)
        ) or "(none)"
        next_line = (
            f"next={nxt.get('title')} / {nxt.get('artist')}"
            if isinstance(nxt, dict)
            else f"next={truth.get('next_status')}"
        )
        line = (
            f"AzuraCast schedule truth: timed_slots={len(slots_t)} "
            f"({truth.get('timed_schedule_status')}); playlists={len(playlists)} [{pl_names}]; "
            f"queue={truth.get('queue_length') or 0}; {next_line}. "
            f"sqlite_grid_used=false."
        )
        return build_live_ops_result(
            "STATION_SCHEDULE",
            packet=packet,
            fallback_line=line,
        )

    if action == "whats_next":
        from services.broadcast.azuracast_client import get_station_schedule_truth

        truth = get_station_schedule_truth(rows=5)
        nxt = truth.get("playing_next")
        if isinstance(nxt, dict) and nxt.get("title"):
            packet = {
                "tool": "whats_next",
                "status": "ok",
                "playing_next": nxt,
                "queue_peek": truth.get("queue_peek") or [],
                "managed_target": "azuracast",
                "neena_role": "separate_agent_product",
            }
            line = (
                f"Next (AzuraCast): title={nxt.get('title')}; artist={nxt.get('artist')}."
            )
            return build_live_ops_result("WHATS_NEXT", packet=packet, fallback_line=line)
        packet = {
            "tool": "whats_next",
            "status": "next_unavailable",
            "reason": "next_unavailable",
            "next_status": truth.get("next_status"),
            "queue_peek": truth.get("queue_peek") or [],
            "managed_target": "azuracast",
            "neena_role": "separate_agent_product",
        }
        return build_live_ops_result(
            "WHATS_NEXT_UNAVAILABLE",
            packet=packet,
            fallback_line=(
                "Cannot invent next song: AzuraCast playing_next unavailable this check. "
                f"queue_length={truth.get('queue_length') or 0}."
            ),
        )

    if action == "assign_capsule_to_playlist":
        from services.broadcast.playback_control import ensure_capsule_playback

        cid_raw = slots.get("capsule_id")
        if cid_raw is None:
            cap = snap.get("latest_ready_for_azuracast") or ((snap.get("latest_capsules") or [None])[0])
            cid_raw = (cap or {}).get("id") if isinstance(cap, dict) else None
        try:
            cid = int(cid_raw) if cid_raw is not None else None
        except (TypeError, ValueError):
            cid = None
        if not cid:
            return build_live_ops_result(
                "ASSIGN_PLAYLIST_BLOCKED",
                packet={
                    "tool": "assign_capsule_to_playlist",
                    "status": "blocked",
                    "reason": "capsule_id_required",
                },
                fallback_line="Assign blocked: capsule_id chahiye (uploaded/approved capsule).",
            )
        playlist_id = slots.get("playlist_id") or slots.get("playlist")
        explicit = bool(slots.get("explicit_approval")) or bool(slots.get("explicit_push"))
        if not explicit:
            return build_live_ops_result(
                "ASSIGN_PLAYLIST_CONFIRM",
                packet={
                    "tool": "assign_capsule_to_playlist",
                    "status": "needs_confirmation",
                    "owner_must_confirm": True,
                    "capsule_id": cid,
                    "playlist_id": playlist_id,
                    "next_step": "reply_haan_or_nahi",
                },
                fallback_line=(
                    f"Confirm required: capsule #{cid} ko AzuraCast playlist"
                    f"{(' #' + str(playlist_id)) if playlist_id else ' (default)'} pe assign. "
                    "Reply haan or nahi."
                ),
                require_confirmation=True,
                capsule_id=cid,
            )
        result = ensure_capsule_playback(
            cid,
            mode="ensure_playlist",
            playlist_id=str(playlist_id) if playlist_id else None,
        )
        ok = bool(result.get("success")) and not result.get("blocked")
        packet = {
            "tool": "assign_capsule_to_playlist",
            "status": "ok" if ok else ("blocked" if result.get("blocked") else "failed"),
            "capsule_id": cid,
            "playlist_id": playlist_id or (result.get("safe_details") or {}).get("playlist_id"),
            "playback_status": result.get("playback_status"),
            "message": result.get("message"),
            "managed_target": "azuracast",
            "neena_role": "separate_agent_product",
        }
        return build_live_ops_result(
            "ASSIGN_PLAYLIST" if ok else "ASSIGN_PLAYLIST_FAILED",
            packet=packet,
            fallback_line=result.get("message")
            or (f"Capsule #{cid} playlist assign {'ok' if ok else 'failed'}."),
            require_confirmation=False,
            capsule_id=cid,
        )

    if action == "capsule_status_clarify":
        return build_live_ops_result(
            "CAPSULE_STATUS_CLARIFY",
            packet={
                "tool": "capsule_status_clarify",
                "status": "needs_clarification",
                "options": ["vm_status", "broadcast_capsule_status"],
            },
            fallback_line="Clarify: VM/cloud machine status, or broadcast capsule status?",
        )

    if action == "model_status":
        from services.llm.model_status import build_model_status_reply

        return {
            "reply": build_model_status_reply(snap),
            "action_type": "MODEL_STATUS",
            "gemini_calls": 0,
        }

    if action == "memory_status":
        from services.memory.status import build_memory_status_reply

        return {
            "reply": build_memory_status_reply(),
            "action_type": "MEMORY_STATUS",
            "gemini_calls": 0,
        }

    if action == "check_interaction_recorder":
        import services.brain.feature_flags as feature_flags
        from services.brain.recorder_review import build_recorder_review

        if not feature_flags.recorder_self_check_enabled():
            packet = {
                "tool": "check_interaction_recorder",
                "enabled": False,
                "flag": "NEENA_RECORDER_SELF_CHECK",
                "note": "Recorder self-check disabled; no recorder edit performed.",
            }
            return build_live_ops_result(
                "RECORDER_CHECK_DISABLED",
                packet=packet,
                fallback_line="Recorder self-check disabled (NEENA_RECORDER_SELF_CHECK).",
            )
        limit = slots.get("limit") or 12
        channel = slots.get("channel")
        try:
            limit_i = int(limit)
        except (TypeError, ValueError):
            limit_i = 12
        review = build_recorder_review(limit=limit_i, channel=channel if channel else None)
        packet = review.get("factual_packet") or {"tool": "check_interaction_recorder"}
        return build_live_ops_result(
            "RECORDER_CHECK",
            packet=packet,
            fallback_line=(
                f"Recorder read-only: {review.get('turn_count') or 0} turns; "
                f"findings={len(review.get('findings') or [])}."
            ),
            recorder_findings=review.get("findings") or [],
            recorder_turn_count=review.get("turn_count") or 0,
            read_only=True,
        )

    if action == "timeout_diagnosis":
        packet, fallback = _timeout_diagnosis_packet(snap)
        return build_live_ops_result("TIMEOUT_DIAGNOSIS", packet=packet, fallback_line=fallback)

    if action == "pipeline_status":
        packet, fallback = _pipeline_status_packet(snap)
        return build_live_ops_result("PIPELINE_STATUS", packet=packet, fallback_line=fallback)

    if action == "explain_button":
        packet, fallback = _explain_button_packet(snap, slots)
        return build_live_ops_result("EXPLAIN_BUTTON", packet=packet, fallback_line=fallback)

    if action == "open_latest_script":
        pending = snap.get("latest_pending_capsule")
        latest = pending or ((snap.get("latest_capsules") or [None])[0])
        if not latest:
            return build_live_ops_result(
                "OPEN_SCRIPT_NONE",
                packet={"tool": "open_latest_script", "status": "none", "next_step": "create_script"},
                fallback_line="No script/capsule found. Create an RJ intro or ad script first.",
            )
        cid = latest.get("id")
        aid = latest.get("approval_queue_id")
        preview = ""
        for p in snap.get("pending_scripts") or []:
            if p.get("id") == aid:
                preview = (p.get("preview") or "")[:200]
                break
        return build_live_ops_result(
            "OPEN_LATEST_SCRIPT",
            packet={
                "tool": "open_latest_script",
                "status": "ok",
                "capsule_id": cid,
                "approval_id": aid,
                "next_step": "review_and_approve",
            },
            fallback_line=f"Opened latest script — Capsule #{cid}. Review then approve.",
            capsule_id=cid,
            approval_id=aid,
            ui_action={
                "type": "open_latest_script",
                "capsule_id": cid,
                "approval_id": aid,
                "tab": "neenalab",
            },
            script_preview=preview,
        )

    if action == "approve_latest_script":
        return _handle_approve_latest_script(snap, slots, owner_message=owner_message)

    if action == "verify_stream":
        # Continuity: if a stream-verify job is still in flight, report it — do not start a twin.
        try:
            from services.agent.working_context import load_working_context
            from services.cockpit.job_repository import get_job

            prev_jid = (load_working_context() or {}).get("last_job_id")
            if prev_jid and not slots.get("force_new"):
                job = get_job(str(prev_jid)) or {}
                st = (job.get("status") or "").lower()
                if st in ("queued", "running", "pending", "in_progress"):
                    msg = (
                        job.get("progress_message")
                        or job.get("owner_message")
                        or f"Stream verification still running (job {prev_jid})."
                    )
                    return build_live_ops_result(
                        "STREAM_VERIFY",
                        packet={
                            "tool": "verify_stream",
                            "status": "in_progress",
                            "job_id": prev_jid,
                            "job_status": st,
                            "message": msg,
                            "reused_existing_job": True,
                        },
                        fallback_line=msg,
                        job_id=prev_jid,
                        ui_action={
                            "type": "poll_cockpit_job",
                            "job_id": prev_jid,
                            "action_key": "verify_latest_stream",
                        },
                    )
                if st in ("completed", "success", "done", "failed", "error") and job:
                    detail = (
                        job.get("owner_message")
                        or job.get("progress_message")
                        or job.get("error_summary")
                        or st
                    )
                    # Owner asked again after finish — return last result; only force_new starts another.
                    if not slots.get("force_new"):
                        return build_live_ops_result(
                            "STREAM_VERIFY",
                            packet={
                                "tool": "verify_stream",
                                "status": st,
                                "job_id": prev_jid,
                                "job_status": st,
                                "message": detail,
                                "reused_existing_job": True,
                            },
                            fallback_line=f"Last stream verify ({prev_jid}): {detail}",
                            job_id=prev_jid,
                        )
        except Exception:
            pass

        res = execute_cockpit_action_for_chat("verify_stream", slots)
        if not res:
            return None
        action_type = res.get("action_type") or "STREAM_VERIFY"
        job_id = res.get("job_id")
        msg = res.get("reply") or "Stream verification started."
        out = build_live_ops_result(
            action_type,
            packet={
                "tool": "verify_stream",
                "status": "started" if job_id else "ok",
                "job_id": job_id,
                "message": msg,
            },
            fallback_line=msg,
            job_id=job_id,
        )
        if job_id:
            out["ui_action"] = {
                "type": "poll_cockpit_job",
                "job_id": job_id,
                "action_key": "verify_latest_stream",
            }
        return out

    if action == "diagnose_listener_path":
        from services.brain.feature_flags import listener_path_tools_enabled
        from services.broadcast.listener_path import diagnose_listener_path

        if not listener_path_tools_enabled():
            return build_live_ops_result(
                "LISTENER_PATH_DISABLED",
                packet={
                    "tool": "diagnose_listener_path",
                    "status": "disabled",
                    "flag": "NEENA_LISTENER_PATH_TOOLS",
                },
                fallback_line="Listener-path tools disabled (NEENA_LISTENER_PATH_TOOLS).",
            )
        diag = diagnose_listener_path()
        needs_confirm = diag.get("verdict") != "healthy" and bool(diag.get("proposed_fix"))
        packet = _listener_diag_packet(diag, owner_must_confirm=needs_confirm)
        fallback = diag.get("message") or f"Listener-path verdict: {diag.get('verdict')}."
        if needs_confirm:
            fallback += " Confirm required to apply known-good URLs (reply haan or nahi)."
        out = build_live_ops_result(
            "DIAGNOSE_LISTENER_PATH",
            packet=packet,
            fallback_line=fallback,
            listener_path=diag,
        )
        if needs_confirm:
            out["require_confirmation"] = True
            out["pending_fix_action"] = "fix_app_listener_path"
            out["pending_fix_slots"] = {
                **(diag.get("proposed_fix") or {}),
                "needs_confirmation": False,
                "explicit_fix": True,
            }
        return out

    if action == "fix_app_listener_path":
        from services.brain.feature_flags import listener_path_tools_enabled
        from services.broadcast.listener_path import (
            diagnose_listener_path,
            propose_known_good_fix,
            set_app_listener_config,
        )
        from services.safety.policy_guard import check_permission

        if not listener_path_tools_enabled():
            return build_live_ops_result(
                "LISTENER_PATH_DISABLED",
                packet={
                    "tool": "fix_app_listener_path",
                    "status": "disabled",
                    "flag": "NEENA_LISTENER_PATH_TOOLS",
                },
                fallback_line="Listener-path tools disabled.",
            )

        explicit = bool(slots.get("explicit_fix")) or any(
            p in (owner_message or "").lower()
            for p in ("theek karo", "fix karo", "url set karo", "kar do", "haan", "yes", "confirm")
        )
        proposed = propose_known_good_fix()
        stream_url = slots.get("stream_url") or proposed.get("stream_url")
        api_base = slots.get("api_base_url") or proposed.get("api_base_url")
        backup = slots.get("backup_stream_url") or proposed.get("backup_stream_url")

        if not explicit and slots.get("needs_confirmation", True):
            return build_live_ops_result(
                "FIX_APP_LISTENER_PATH_CONFIRM",
                packet={
                    "tool": "fix_app_listener_path",
                    "status": "needs_confirmation",
                    "owner_must_confirm": True,
                    "stream_url": stream_url,
                    "api_base_url": api_base,
                    "next_step": "reply_haan_or_nahi",
                },
                fallback_line=(
                    f"Confirm required: update app remote config "
                    f"(stream_url={stream_url}, api_base_url={api_base}). Reply haan or nahi."
                ),
                require_confirmation=True,
            )

        perm = check_permission("owner", "set_app_listener_config", has_confirmation=True)
        if not perm.get("allowed"):
            return build_live_ops_result(
                "FIX_APP_LISTENER_PATH_BLOCKED",
                packet={
                    "tool": "fix_app_listener_path",
                    "status": "blocked",
                    "message": perm.get("message"),
                },
                fallback_line=perm.get("message") or "App config update blocked by policy.",
            )

        result = set_app_listener_config(
            stream_url=stream_url,
            api_base_url=api_base,
            backup_stream_url=backup,
            confirmed=True,
        )
        if not result.get("success"):
            return build_live_ops_result(
                "FIX_APP_LISTENER_PATH_FAILED",
                packet={
                    "tool": "fix_app_listener_path",
                    "status": "failed",
                    "message": result.get("message"),
                },
                fallback_line=result.get("message") or "App config update failed.",
            )
        diag = diagnose_listener_path()
        return build_live_ops_result(
            "FIX_APP_LISTENER_PATH",
            packet={
                "tool": "fix_app_listener_path",
                "status": "ok",
                "message": result.get("message"),
                "recheck": _listener_diag_packet(diag),
            },
            fallback_line=f"{result.get('message')} Re-check verdict: {diag.get('verdict')}.",
            listener_path=diag,
            ui_action={"type": "refresh_cockpit"},
        )

    if action == "generate_audio":
        cap = snap.get("latest_approved_needs_audio")
        if not cap:
            cap = snap.get("latest_pending_capsule")
        if not cap or cap.get("approval_status") != "approved":
            return build_live_ops_result(
                "GENERATE_AUDIO_BLOCKED",
                packet={
                    "tool": "generate_audio",
                    "status": "blocked",
                    "reason": "script_not_approved",
                    "next_step": "approve_script_first",
                },
                fallback_line="Audio blocked: approve a script first.",
            )
        cid = int(cap.get("id"))
        try:
            from services.voice.gen_service import generate_capsule_audio

            result = generate_capsule_audio(cid)
            if result.get("success"):
                return build_live_ops_result(
                    "GENERATE_AUDIO",
                    packet={
                        "tool": "generate_audio",
                        "status": "ok",
                        "capsule_id": cid,
                        "audio_truth_level": result.get("audio_truth_level"),
                    },
                    fallback_line=(
                        f"Audio generated for Capsule #{cid} "
                        f"({result.get('audio_truth_level', 'audio')})."
                    ),
                    capsule_id=cid,
                    ui_action={"type": "refresh_cockpit"},
                )
            return build_live_ops_result(
                "GENERATE_AUDIO_FAILED",
                packet={
                    "tool": "generate_audio",
                    "status": "failed",
                    "capsule_id": cid,
                    "message": result.get("message"),
                },
                fallback_line=result.get("message") or f"Capsule #{cid} audio generate failed.",
            )
        except Exception as exc:
            logger.error("generate_audio live ops failed: %s", exc)
            return build_live_ops_result(
                "GENERATE_AUDIO_ERROR",
                packet={
                    "tool": "generate_audio",
                    "status": "error",
                    "error_type": type(exc).__name__,
                },
                fallback_line=f"Audio generate error: {type(exc).__name__}",
            )

    if action == "send_azuracast":
        from services.broadcast.capsule_service import (
            get_capsule_by_id,
            enrich_capsule_for_api,
            send_capsule_to_azuracast,
        )

        cap = None
        slot_cid = slots.get("capsule_id")
        if slot_cid is not None:
            try:
                raw = get_capsule_by_id(int(slot_cid))
                if raw:
                    cap = enrich_capsule_for_api(raw)
            except (TypeError, ValueError):
                cap = None
            if cap and not cap.get("azuracast_push_allowed"):
                reason = cap.get("azuracast_push_block_reason") or "approval + real audio required"
                return build_live_ops_result(
                    "SEND_AZURACAST_BLOCKED",
                    packet={
                        "tool": "send_azuracast",
                        "status": "blocked",
                        "capsule_id": cap.get("id"),
                        "reason": reason,
                    },
                    fallback_line=f"AzuraCast push blocked for Capsule #{cap.get('id')}: {reason}.",
                    capsule_id=cap.get("id"),
                )
        if not cap:
            cap = snap.get("latest_ready_for_azuracast")
        if not cap:
            reason = None
            caps = snap.get("latest_capsules") or []
            if caps:
                reason = caps[0].get("azuracast_push_block_reason")
            return build_live_ops_result(
                "SEND_AZURACAST_BLOCKED",
                packet={
                    "tool": "send_azuracast",
                    "status": "blocked",
                    "reason": reason or "approval + real audio required",
                },
                fallback_line=f"AzuraCast push blocked: {reason or 'approval + real audio required'}.",
            )
        explicit = bool(slots.get("explicit_push")) or bool(slots.get("explicit_approval"))
        if not explicit:
            cid = cap.get("id")
            return build_live_ops_result(
                "SEND_AZURACAST_CONFIRM",
                packet={
                    "tool": "send_azuracast",
                    "status": "needs_confirmation",
                    "owner_must_confirm": True,
                    "capsule_id": cid,
                    "next_step": "reply_haan_or_nahi",
                },
                fallback_line=f"Confirm required: AzuraCast push capsule #{cid}. Reply haan or nahi.",
                require_confirmation=True,
                capsule_id=cid,
            )
        cid = int(cap.get("id"))
        result = send_capsule_to_azuracast(cid)
        if result.get("success"):
            return build_live_ops_result(
                "SEND_AZURACAST",
                packet={
                    "tool": "send_azuracast",
                    "status": "ok",
                    "capsule_id": cid,
                    "next_step": "verify_stream",
                },
                fallback_line=f"Capsule #{cid} uploaded to AzuraCast. Next: Verify Stream.",
                capsule_id=cid,
                ui_action={"type": "refresh_cockpit"},
            )
        return build_live_ops_result(
            "SEND_AZURACAST_FAILED",
            packet={
                "tool": "send_azuracast",
                "status": "failed",
                "capsule_id": cid,
                "message": result.get("message"),
            },
            fallback_line=result.get("message") or "AzuraCast upload failed.",
            capsule_id=cid,
        )

    if action == "ensure_playback":
        # Same continuity as verify_stream: reuse in-flight stream job.
        try:
            from services.agent.working_context import load_working_context
            from services.cockpit.job_repository import get_job

            prev_jid = (load_working_context() or {}).get("last_job_id")
            if prev_jid and not slots.get("force_new"):
                job = get_job(str(prev_jid)) or {}
                st = (job.get("status") or "").lower()
                if st in ("queued", "running", "pending", "in_progress"):
                    msg = (
                        job.get("progress_message")
                        or job.get("owner_message")
                        or f"Stream/playback verify still running (job {prev_jid})."
                    )
                    return build_live_ops_result(
                        "ENSURE_PLAYBACK",
                        packet={
                            "tool": "ensure_playback",
                            "status": "in_progress",
                            "job_id": prev_jid,
                            "job_status": st,
                            "message": msg,
                            "reused_existing_job": True,
                        },
                        fallback_line=msg,
                        job_id=prev_jid,
                        ui_action={
                            "type": "poll_cockpit_job",
                            "job_id": prev_jid,
                            "action_key": "verify_latest_stream",
                        },
                    )
        except Exception:
            pass
        cap = snap.get("latest_ready_for_azuracast") or ((snap.get("latest_capsules") or [None])[0])
        if not cap:
            return build_live_ops_result(
                "ENSURE_PLAYBACK_BLOCKED",
                packet={
                    "tool": "ensure_playback",
                    "status": "blocked",
                    "reason": "need_approved_audio_and_azuracast_upload",
                },
                fallback_line="Playback ensure blocked: need approved audio + AzuraCast upload first.",
            )
        cid = int(cap.get("id"))
        # Default 0 = one-shot + optional short webhook wait (no 30–60s poll theatre).
        res = dispatch_cockpit_action(
            "verify_latest_stream",
            watch_seconds=int(slots.get("watch_seconds") or 8),
        )
        job_id = res.get("job_id")
        msg = res.get("message") or f"Capsule #{cid} playback verify started."
        return build_live_ops_result(
            "ENSURE_PLAYBACK",
            packet={
                "tool": "ensure_playback",
                "status": "started" if job_id else "ok",
                "capsule_id": cid,
                "job_id": job_id,
                "message": msg,
            },
            fallback_line=msg,
            job_id=job_id,
            ui_action={
                "type": "poll_cockpit_job",
                "job_id": job_id,
                "action_key": "verify_latest_stream",
            }
            if job_id
            else {"type": "refresh_cockpit"},
        )

    if action == "list_pending_capsules":
        from services.broadcast.capsule_service import list_recent_capsules
        capsules = list_recent_capsules(limit=10)
        pending = [c for c in capsules if c.get("status") in ("pending_approval", "pending_review", "pending")]
        if not pending:
            return build_live_ops_result(
                "LIST_PENDING_CAPSULES",
                packet={"tool": "list_pending_capsules", "status": "none", "count": 0},
                fallback_line="No pending scripts for review.",
            )
        items = [
            {"id": c.get("id"), "title": c.get("title") or c.get("capsule_type")}
            for c in pending
        ]
        ids = ", ".join(f"#{i['id']} ({i['title']})" for i in items)
        return build_live_ops_result(
            "LIST_PENDING_CAPSULES",
            packet={
                "tool": "list_pending_capsules",
                "status": "ok",
                "count": len(items),
                "pending": items,
            },
            fallback_line=f"Pending review: {ids}.",
            ui_action={"type": "refresh_cockpit"},
        )

    if action in ("open_latest_capsule", "open_latest_script"):
        pending = snap.get("latest_pending_capsule")
        latest = pending or ((snap.get("latest_capsules") or [None])[0])
        if not latest:
            return build_live_ops_result(
                "OPEN_SCRIPT_NONE",
                packet={"tool": "open_latest_capsule", "status": "none", "next_step": "create_script"},
                fallback_line="No script/capsule found. Create an RJ intro or ad script first.",
            )
        cid = latest.get("id")
        aid = latest.get("approval_queue_id")
        preview = ""
        for p in snap.get("pending_scripts") or []:
            if p.get("id") == aid:
                preview = (p.get("preview") or "")[:200]
                break
        return build_live_ops_result(
            "OPEN_LATEST_CAPSULE",
            packet={
                "tool": "open_latest_capsule",
                "status": "ok",
                "capsule_id": cid,
                "approval_id": aid,
                "next_step": "review_and_approve",
            },
            fallback_line=f"Opened latest script — Capsule #{cid}. Review then approve.",
            capsule_id=cid,
            approval_id=aid,
            ui_action={
                "type": "open_latest_script",
                "capsule_id": cid,
                "approval_id": aid,
                "tab": "neenalab",
            },
            script_preview=preview,
        )

    if action in ("approve_capsule", "approve_latest_script"):
        target_id = slots.get("capsule_id") or slots.get("id")
        if target_id:
            try:
                target_id = int(target_id)
            except ValueError:
                target_id = None
        return _handle_approve_capsule(snap, target_id, slots, owner_message=owner_message)

    if action == "reject_capsule":
        target_id = slots.get("capsule_id") or slots.get("id")
        if target_id:
            try:
                target_id = int(target_id)
            except ValueError:
                target_id = None
        reason = slots.get("reject_reason") or slots.get("reason") or "No reason provided"
        rejected_by = slots.get("rejected_by") or "owner"
        return _handle_reject_capsule(snap, target_id, reason, rejected_by)

    if action == "needs_revision":
        target_id = slots.get("capsule_id") or slots.get("id")
        if target_id:
            try:
                target_id = int(target_id)
            except ValueError:
                target_id = None
        reason = slots.get("reason") or slots.get("reject_reason") or "Revision requested"
        return _handle_needs_revision(snap, target_id, reason=reason)

    if action in ("prepare_capsule_audio", "generate_audio"):
        target_id = slots.get("capsule_id") or slots.get("id")
        if target_id:
            try:
                target_id = int(target_id)
            except ValueError:
                target_id = None
        return _handle_prepare_audio(snap, target_id)

    if action == "propose_permanent_memory":
        from services.llm.intent_router import is_affirmative_reply, is_confirmation_only
        from services.memory.facade import propose_write
        from services.memory.edit_service import get_pending_memory_edit
        import services.memory.service as memory_service

        # Legacy pending leftover: clear and continue — owner directives autosave now.
        if memory_service.get_pending_permanent_memory_candidate():
            memory_service.cancel_pending_permanent_memory_candidate()
        if get_pending_memory_edit():
            return build_live_ops_result(
                "PROPOSE_PERMANENT_MEMORY_BLOCKED",
                packet={
                    "tool": "propose_permanent_memory",
                    "status": "blocked_pending_edit",
                    "reason": "memory_edit_already_pending",
                    "next_step": "reply_haan_or_nahi",
                },
                fallback_line=(
                    "Memory edit/delete already pending confirmation. "
                    "Reply haan or nahi for that change first."
                ),
                require_confirmation=True,
                ok=False,
            )

        content = (
            slots.get("content")
            or slots.get("memory_content")
            or slots.get("text")
            or ""
        ).strip()
        mtype = slots.get("memory_type")
        if not content:
            content = (owner_message or "").strip()
        content_l = content.lower().strip().strip(".!,?")
        if (
            not content
            or is_confirmation_only(content_l)
            or is_affirmative_reply(content_l)
            or memory_service.is_memory_rejection_message(content_l)
        ):
            return build_live_ops_result(
                "PROPOSE_PERMANENT_MEMORY_NEEDS_CONTENT",
                packet={
                    "tool": "propose_permanent_memory",
                    "status": "needs_content",
                    "reason": "content_missing_or_confirm_only",
                },
                fallback_line=(
                    "Permanent memory content missing. "
                    "Send one clear line to save (not just haan/nahi)."
                ),
                ok=False,
            )
        res = propose_write(
            role="owner",
            content=content,
            memory_type=mtype,
            source_message=owner_message or content,
            subject_key="owner",
        )
        packet = {
            "tool": "propose_permanent_memory",
            "status": res.get("status") or ("ok" if res.get("ok") else "blocked"),
            "owner_must_confirm": False,
            "saved": res.get("status") == "saved",
            "candidate": (res.get("candidate") or {}).get("content"),
            "memory_type": (res.get("candidate") or {}).get("memory_type"),
            "postgres_memory_id": res.get("postgres_memory_id"),
            "sqlite_memory_id": res.get("sqlite_memory_id"),
            "intent_hint": "acknowledge_saved_preference" if res.get("status") == "saved" else None,
        }
        if isinstance(res.get("factual_packet"), dict):
            packet.update(res["factual_packet"])
        return build_live_ops_result(
            res.get("action_type") or "PROPOSE_PERMANENT_MEMORY",
            packet=packet,
            fallback_line=res.get("reply") or "Permanent memory write failed.",
            require_confirmation=False,
            ok=bool(res.get("ok")),
            factual_packet=packet,
        )

    if action == "capsule_status":
        target_id = slots.get("capsule_id") or slots.get("id")
        if target_id:
            try:
                target_id = int(target_id)
            except ValueError:
                target_id = None

        from services.broadcast.capsule_service import get_capsule_by_id, get_latest_capsule
        cap = get_capsule_by_id(target_id) if target_id else get_latest_capsule()
        if not cap:
            return build_live_ops_result(
                "CAPSULE_STATUS_NONE",
                packet={"tool": "capsule_status", "status": "none"},
                fallback_line="No capsule found for status check.",
            )
        cid = cap.get("id")
        status = cap.get("status") or "draft"
        audio = cap.get("audio_status") or "none"
        az = cap.get("azuracast_status") or "blocked"
        return build_live_ops_result(
            "CAPSULE_STATUS",
            packet={
                "tool": "capsule_status",
                "status": "ok",
                "capsule_id": cid,
                "approval": status,
                "audio": audio,
                "azuracast": az,
            },
            fallback_line=f"Capsule #{cid}: approval={status}, audio={audio}, azuracast={az}.",
            capsule_id=cid,
            status=status,
            audio_status=audio,
            azuracast_status=az,
        )

    return None


def run_action(action: str, ctx) -> dict | None:
    """Adapter used by category modules."""
    return dispatch_impl(
        action,
        ctx.slots,
        snapshot=ctx.snapshot,
        owner_message=ctx.owner_message or "",
    )

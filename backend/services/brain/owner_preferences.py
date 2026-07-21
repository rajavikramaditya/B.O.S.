"""Owner preference + owner WhatsApp push handlers (extracted from neena_brain).

Preference / time replies are factual packets — humanize elsewhere.
"""
from __future__ import annotations

import re

from services.llm.intent_router import is_whatsapp_message_request


def handle_set_response_style(verbosity: str) -> tuple[str, bool, dict]:
    """Apply owner verbosity preference. Returns (fallback, concise_flag, factual_packet)."""
    import services.brain.manager_state as manager_state

    concise = verbosity in ("short", "brief", "concise", "chhota", "small", "kam")
    manager_state.set_response_style(concise)
    packet = {
        "tool": "set_response_style",
        "status": "ok",
        "concise": concise,
        "verbosity": "short" if concise else "detail",
    }
    fallback = f"Response style set. concise={concise}."
    return fallback, concise, packet


def handle_send_owner_whatsapp_status(interp_packet: dict, live_snapshot: dict | None) -> tuple[str, dict]:
    """Push station status to owner WhatsApp. Return (fallback, factual_packet)."""
    import services.brain.owner_notifier

    del interp_packet, live_snapshot

    if not owner_notifier.get_owner_digits():
        packet = {
            "tool": "send_owner_whatsapp_status",
            "status": "not_configured",
            "sent": False,
            "reason": "OWNER_WHATSAPP_NUMBER_missing",
        }
        return (
            "Owner WhatsApp not configured (OWNER_WHATSAPP_NUMBER missing). Status not sent.",
            packet,
        )
    try:
        from services.cockpit.status_fast import (
            get_cockpit_status_snapshot,
            format_station_status_message,
        )

        snapshot = get_cockpit_status_snapshot(allow_stream_probe=False, include_capsules=False)
        status_text = format_station_status_message(snapshot)
    except Exception:
        status_text = "Orai Radio status: backend online. Detail unavailable."

    sent = owner_notifier.notify_owner(status_text)
    packet = {
        "tool": "send_owner_whatsapp_status",
        "status": "sent" if sent else "gateway_failed",
        "sent": bool(sent),
        "status_chars": len(status_text or ""),
    }
    if sent:
        return "Owner WhatsApp status push sent.", packet
    return (
        f"Owner WhatsApp gateway failed. Status not delivered.\n{status_text}",
        packet,
    )


def try_handle_interpreter_action(
    action: str,
    interp_packet: dict,
    live_snapshot: dict | None,
    message: str,
    tb,
    save_fn,
) -> dict | None:
    """Handle set_response_style / send_owner_whatsapp_status. None if not matched."""
    if action == "set_response_style":
        verbosity = str((interp_packet.get("slots") or {}).get("verbosity") or "").strip().lower()
        reply, _concise, packet = handle_set_response_style(verbosity)
        tb.source = "local_router"
        tb.route = "set_response_style"
        tb.final_reply_source = "command_interpreter"
        return save_fn(
            message,
            reply,
            action_type="SET_RESPONSE_STYLE",
            factual_packet=packet,
            _tb=tb,
        )

    if action == "send_owner_whatsapp_status":
        tb.source = "local_router"
        tb.route = "send_owner_whatsapp_status"
        tb.final_reply_source = "command_interpreter"
        reply, packet = handle_send_owner_whatsapp_status(interp_packet, live_snapshot)
        return save_fn(
            message,
            reply,
            action_type="send_owner_whatsapp_status",
            factual_packet=packet,
            _tb=tb,
        )

    if action == "time_status":
        from datetime import datetime, timedelta, timezone

        ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        packet = {
            "tool": "time_status",
            "timezone": "Asia/Kolkata",
            "iso_ist": ist.isoformat(),
            "weekday": ist.strftime("%A"),
            "date": ist.strftime("%Y-%m-%d"),
            "time": ist.strftime("%H:%M"),
        }
        fallback = (
            f"Time status IST. weekday={packet['weekday']} date={packet['date']} "
            f"time={packet['time']}."
        )
        tb.source = "local_router"
        tb.route = "time_status"
        tb.final_reply_source = "local_action"
        return save_fn(
            message,
            fallback,
            action_type="TIME_STATUS",
            factual_packet=packet,
            _tb=tb,
        )

    if action == "manage_memory":
        from services.memory.edit_service import create_pending_memory_edit

        slots = interp_packet.get("slots") or {}
        res = create_pending_memory_edit(slots.get("operation"), slots.get("target"), slots.get("new_content"))
        tb.source = "local_router"
        tb.route = "manage_memory"
        tb.final_reply_source = "local_action"
        return save_fn(
            message,
            res["reply"],
            action_type=res.get("action_type") or "MANAGE_MEMORY",
            require_confirmation=bool(res.get("require_confirmation")),
            factual_packet=res.get("factual_packet") if isinstance(res.get("factual_packet"), dict) else None,
            _tb=tb,
        )

    return None


def try_handle_exact_path_whatsapp_send(message: str, msg_lower: str, tb, save_fn) -> dict | None:
    """Exact-command path: owner-self WhatsApp status push; block arbitrary outbound."""
    if not is_whatsapp_message_request(msg_lower):
        return None
    if re.search(r"\b\d{10,15}\b", msg_lower) and len(message.split()) > 4:
        tb.source = "local_router"
        tb.route = "clarification"
        tb.step("response", "Arbitrary WhatsApp outbound with phone number — blocked")
        packet = {
            "tool": "whatsapp_outbound",
            "status": "blocked",
            "reason": "arbitrary_outbound_not_available",
        }
        reply = "Arbitrary outbound WhatsApp with phone number is not available. No fake delivery claim."
        return save_fn(
            message,
            reply,
            action_type="clarification",
            factual_packet=packet,
            _tb=tb,
        )
    tb.source = "local_router"
    tb.route = "send_owner_whatsapp_status"
    tb.step("response", "Owner WhatsApp status push (local path)")
    reply, packet = handle_send_owner_whatsapp_status({}, None)
    return save_fn(
        message,
        reply,
        action_type="send_owner_whatsapp_status",
        factual_packet=packet,
        _tb=tb,
    )


__all__ = [
    "handle_set_response_style",
    "handle_send_owner_whatsapp_status",
    "try_handle_interpreter_action",
    "try_handle_exact_path_whatsapp_send",
]

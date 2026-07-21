"""Builtin owner tool definitions — metadata only; handlers bind from live_ops.

New tools: add a module under services/tools/, call register(ToolSpec(...)),
and import it from load_all(). Do not edit VALID_ACTIONS / SAFE_FOLLOWUP frozensets.
"""
from __future__ import annotations

from services.tools.catalog import ToolSpec, register

# Aliases previously in command_execution_kernel._ACTION_ALIASES
_COMMON_ALIASES = {
    "what_now": "what_should_i_do_now",
    "status": "station_status",
    "diagnostics_fast": "diagnostics",
    "show_latest_script": "open_latest_script",
    "pending_scripts": "pipeline_status",
    "daily_show_plan": "create_station_plan",
}


def _reg(
    tool_id: str,
    description: str,
    *,
    risk: str,
    route: str,
    followup_ok: bool = False,
    category: str = "general",
    slot_hint: str = "",
    aliases: tuple[str, ...] = (),
    capability_label: str | None = None,
) -> None:
    extra = tuple(a for a, dest in _COMMON_ALIASES.items() if dest == tool_id)
    register(
        ToolSpec(
            id=tool_id,
            description=description,
            risk=risk,
            route=route,
            followup_ok=followup_ok,
            aliases=aliases + extra,
            slot_hint=slot_hint,
            category=category,
            capability_label=capability_label or description,
        )
    )


def register_builtin_definitions() -> None:
    """Idempotent: register() replaces by id."""

    # --- cockpit ---
    _reg(
        "station_status",
        "System/station health and status",
        risk="read",
        route="cockpit",
        followup_ok=True,
        category="status",
        slot_hint="requested_scope (full|short|health_only)",
    )
    _reg(
        "diagnostics",
        "Diagnostics / health scan",
        risk="read",
        route="cockpit",
        followup_ok=True,
        category="diagnostics",
    )

    # --- prefs (brain short-circuit; time_status also mid-loop via live bridge) ---
    _reg(
        "set_response_style",
        "Owner reply-length preference (short/normal)",
        risk="safe_write",
        route="prefs",
        category="prefs",
        slot_hint='verbosity ("short"|"normal")',
    )
    _reg(
        "send_owner_whatsapp_status",
        "Push station status to owner WhatsApp",
        risk="confirm_required",
        route="prefs",
        category="prefs",
        slot_hint='topic ("status" | free text)',
    )
    _reg(
        "time_status",
        "Current IST date/time",
        risk="read",
        route="prefs",
        followup_ok=True,
        category="status",
    )
    _reg(
        "manage_memory",
        "List/update/delete saved permanent memories",
        risk="confirm_required",
        route="prefs",
        category="memory",
        slot_hint='operation ("list"|"update"|"delete"), target, new_content',
    )

    # --- creative ---
    _reg(
        "create_rj_intro",
        "Generate RJ intro script",
        risk="safe_write",
        route="creative",
        category="creative",
        slot_hint="show_time, tone, local_touch_requested, length_preference",
    )
    _reg(
        "create_ad_script",
        "Generate ad script",
        risk="safe_write",
        route="creative",
        category="creative",
        slot_hint="business_name, duration_seconds, tone, cta_preference",
    )
    # create_daily_show_plan retired as creative capsule — see tools/station_plan.py
    # (living Station Clock plan; alias create_daily_show_plan → create_station_plan).
    _reg(
        "create_broadcast_capsule",
        "Create broadcast capsule / morning update script",
        risk="safe_write",
        route="creative",
        category="creative",
        slot_hint="topic, language, tone, creator",
    )

    # --- live_ops reads ---
    _reg(
        "capabilities",
        "List what Neena can manage / tool capabilities",
        risk="read",
        route="live_ops",
        category="status",
    )
    _reg(
        "model_status",
        "Model/brain/cooldown/rate-limit status",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="status",
    )
    _reg(
        "memory_status",
        "Memory stack health (Postgres/Redis/pgvector)",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="memory",
    )
    _reg(
        "timeout_diagnosis",
        "Why commands are slow or timing out",
        risk="read",
        route="live_ops",
        category="diagnostics",
    )
    _reg(
        "what_should_i_do_now",
        "Recommended next station action",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="status",
    )
    _reg(
        "pipeline_status",
        "Pending scripts / approval queue / broadcast pipeline",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="pipeline",
    )
    _reg(
        "explain_button",
        "Explain a Command Center UI button",
        risk="read",
        route="live_ops",
        category="status",
        slot_hint="button_name or button_id (approve|audio|azuracast|verify|status)",
    )
    _reg(
        "open_latest_script",
        "Open latest/pending script for review",
        risk="read",
        route="live_ops",
        category="pipeline",
    )
    _reg(
        "verify_stream",
        "Verify on-air stream health",
        risk="read",
        route="live_ops",
        category="diagnostics",
        slot_hint="watch_seconds (optional int)",
    )
    _reg(
        "list_pending_capsules",
        "List capsules pending review",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="capsule",
    )
    _reg(
        "open_latest_capsule",
        "Open latest capsule",
        risk="read",
        route="live_ops",
        category="capsule",
    )
    _reg(
        "capsule_status",
        "Capsule approval/audio/azuracast status",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="capsule",
        slot_hint="capsule_id (optional int)",
    )
    _reg(
        "capsule_status_clarify",
        "Clarify VM status vs capsule status",
        risk="read",
        route="live_ops",
        category="capsule",
    )
    _reg(
        "admin_lock",
        "Lock Command Center (owner phrase to unlock)",
        risk="safe_write",
        route="live_ops",
        category="auth",
    )
    _reg(
        "auth_session_explain",
        "Explain unlock cookie / session lock behavior",
        risk="read",
        route="live_ops",
        category="auth",
    )
    _reg(
        "vm_status",
        "VM / cloud machine status",
        risk="read",
        route="live_ops",
        category="status",
    )
    _reg(
        "now_playing",
        "What is on air now (AzuraCast now-playing — managed target, not Neena body)",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="status",
        aliases=("whats_playing", "on_air", "ab_kya_chal_raha"),
        capability_label="Now playing (AzuraCast)",
    )
    _reg(
        "get_station_schedule",
        "AzuraCast schedule/playlists/queue/next truth (never SQLite fake grid)",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="status",
        aliases=("station_schedule", "list_playlists", "aaj_schedule"),
        capability_label="Station schedule (AzuraCast)",
        slot_hint="rows (optional 1-50)",
    )
    _reg(
        "whats_next",
        "Next cued item from AzuraCast playing_next (honest next_unavailable if missing)",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="status",
        aliases=("playing_next", "agla_kya"),
        capability_label="What's next (AzuraCast)",
    )
    _reg(
        "check_interaction_recorder",
        "Read-only interaction recorder self-check",
        risk="read",
        route="live_ops",
        followup_ok=True,
        category="diagnostics",
        slot_hint="limit (optional 3-30), channel (optional chat|whatsapp)",
        capability_label="Recorder self-check",
    )
    _reg(
        "diagnose_listener_path",
        "Diagnose public app listener path (no URL write)",
        risk="read",
        route="live_ops",
        category="diagnostics",
    )

    # --- live_ops writes (confirm) ---
    _reg(
        "approve_latest_script",
        "Approve latest pending script",
        risk="confirm_required",
        route="live_ops",
        category="pipeline",
        slot_hint="explicit_approval (bool)",
    )
    _reg(
        "generate_audio",
        "Generate/prepare capsule audio (explicit audio only)",
        risk="confirm_required",
        route="live_ops",
        category="broadcast",
    )
    _reg(
        "send_azuracast",
        "Push capsule to AzuraCast / broadcast",
        risk="confirm_required",
        route="live_ops",
        category="broadcast",
    )
    _reg(
        "ensure_playback",
        "Confirm playback is running on air",
        risk="confirm_required",
        route="live_ops",
        category="broadcast",
    )
    _reg(
        "assign_capsule_to_playlist",
        "Assign uploaded capsule media to an AzuraCast playlist (confirm)",
        risk="confirm_required",
        route="live_ops",
        category="broadcast",
        slot_hint="capsule_id, playlist_id (optional), explicit_approval",
        aliases=("assign_playlist", "playlist_me_lagao"),
        capability_label="Assign capsule → playlist",
    )
    _reg(
        "approve_capsule",
        "Approve a capsule",
        risk="confirm_required",
        route="live_ops",
        category="capsule",
        slot_hint="capsule_id (optional), approved_by (optional)",
    )
    _reg(
        "reject_capsule",
        "Reject a capsule",
        risk="confirm_required",
        route="live_ops",
        category="capsule",
        slot_hint="capsule_id, reject_reason",
    )
    _reg(
        "prepare_capsule_audio",
        "Prepare audio for approved capsule",
        risk="confirm_required",
        route="live_ops",
        category="broadcast",
        slot_hint="capsule_id (optional)",
    )
    _reg(
        "needs_revision",
        "Mark capsule needs revision",
        risk="confirm_required",
        route="live_ops",
        category="capsule",
    )
    _reg(
        "fix_app_listener_path",
        "Apply known-good app stream/API URLs (confirm)",
        risk="confirm_required",
        route="live_ops",
        category="diagnostics",
    )
    _reg(
        "propose_permanent_memory",
        "Propose NEW permanent memory (confirm to save)",
        risk="confirm_required",
        route="live_ops",
        category="memory",
        slot_hint="content, memory_type (optional)",
    )


__all__ = ["register_builtin_definitions"]

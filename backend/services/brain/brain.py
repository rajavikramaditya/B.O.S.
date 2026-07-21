import os
import sys
import re
import json
import time
import logging
from datetime import datetime
from typing import Any, Literal

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
import services.cockpit.runtime_controller as rc
import services.tools.legacy_gemini_registry as tr
import services.llm.provider_router as pr

# Modular imports (Phase B)
from services.llm.intent_router import (
    is_confirmation_only,
    is_affirmative_reply,
    contains_forbidden_command,
)
import services.llm.intent_llm as intent_llm
import services.safety.policy_guard as policy_guard
import services.brain.context_builder as context_builder
import services.brain.response_composer as response_composer
import services.memory.adapter as memory_adapter
import services.brain.manager_state as manager_state
import services.memory.service as memory_service
from services.brain.always_reply import ensure_nonempty_reply
import services.memory.edit_service as memory_edit_service
import services.brain.operations_workflows as operations_workflows
import services.safety.policy_engine as policy_engine
import services.brain.feature_flags as feature_flags
import services.brain.owner_preferences as owner_preferences
from services.brain.trace_builder import _TraceBuilder
from services.brain.prompt_builder import build_response_system_prompt, build_policy_context_block, build_24hr_plan_prompt
from services.tools.executor import run_diagnostics_command, format_whatsapp_status_reply, format_center_status_reply, format_source_tools_status

logger = logging.getLogger(__name__)

# Trace / Metadata Builder (Extracted to neena_trace_builder.py)

# One-tap owner confirmation. After Neena surfaces a protected action for
# confirmation, a plain "haan / kar do / yes" executes it — the owner does not
# need to re-type the exact phrase. Reversible actions never enter this set; they
# auto-execute without any confirmation. The Safety Kernel still gates execution.
_ONE_TAP_PROTECTED_ACTIONS = frozenset({
    "send_azuracast",
    "approve_latest_script",
    "approve_capsule",
    "fix_app_listener_path",
    "assign_capsule_to_playlist",
    "ensure_playback",
    "generate_audio",
    "prepare_capsule_audio",
})

_ONE_TAP_CANCEL_PHRASES = (
    "nahi", "nahin", "mat karo", "mat karna", "cancel", "rehne do", "rahne do",
    "ruk", "ruko", "stop", "abhi nahi", "abort", "chhodo", "chhod do",
)

def _hand_off_customer_recall(
    message: str,
    *,
    _tb: "_TraceBuilder | None" = None,
) -> tuple[str, dict, str]:
    """Sole owner-facing customer-fact voice: customer_whatsapp_recall module."""
    from services.brain.owner_customer_context import build_customer_recall_packet

    out = build_customer_recall_packet(owner_message=message or "")
    reply = (
        out.get("fallback_line")
        or "Sir, customer WhatsApp check kiya."
    )
    packet = out.get("factual_packet") if isinstance(out.get("factual_packet"), dict) else {
        "tool": "customer_whatsapp_recall",
        "status": "empty",
        "checked": True,
    }
    if _tb is not None:
        try:
            _tb.final_reply_source = "customer_whatsapp_recall"
            _tb.route = "customer_whatsapp_recall"
        except Exception:
            pass
    return reply, packet, "CUSTOMER_WHATSAPP_RECALL"


def _apply_truth_scrub(
    message: str,
    reply: str,
    *,
    factual_packet,
    action_type,
    _tb: "_TraceBuilder | None",
) -> tuple[str, Any, Any]:
    """Scrub invented claims; customer empty-claims hand off to recall module only."""
    from services.agent.truth_gate import NEEDS_CUSTOMER_RECALL, enforce_truth_on_reply

    reply2, scrub_pkt = enforce_truth_on_reply(
        message,
        reply,
        factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
        action=action_type,
    )
    if not scrub_pkt:
        return reply2, factual_packet, action_type
    if scrub_pkt.get("reason") == NEEDS_CUSTOMER_RECALL:
        try:
            return _hand_off_customer_recall(message, _tb=_tb)
        except Exception:
            pass
    if not isinstance(factual_packet, dict) or not factual_packet:
        factual_packet = scrub_pkt
    action_type = action_type or "CANNOT"
    if _tb is not None:
        try:
            _tb.final_reply_source = "truth_gate"
        except Exception:
            pass
    return reply2, factual_packet, action_type


def _save_and_return(message: str, reply: str, command_triggered=None, action_type=None,
                     require_confirmation: bool = False, approval_id=None, capsule_id=None,
                     approval_status=None, audio_truth_level=None, azuracast_status=None,
                     factual_packet=None, job_id=None,
                     _tb: "_TraceBuilder | None" = None) -> dict:
    # job_id alone counts as this-turn work facts for the truth firewall.
    if job_id:
        if not isinstance(factual_packet, dict) or not factual_packet:
            factual_packet = {
                "tool": "background_job",
                "status": "accepted",
                "job_id": job_id,
            }
        elif not factual_packet.get("job_id"):
            factual_packet = {**factual_packet, "job_id": job_id}
    try:
        reply, factual_packet, action_type = _apply_truth_scrub(
            message,
            reply,
            factual_packet=factual_packet,
            action_type=action_type,
            _tb=_tb,
        )
    except Exception:
        pass
    reply = ensure_nonempty_reply(
        response_composer.maybe_humanize_report(
            message,
            reply,
            action_type,
            concise=manager_state.is_concise_mode(),
            factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
        )
    )
    # Humanize can reintroduce fake outbound / empty-customer claims — scrub again.
    try:
        reply, factual_packet, action_type = _apply_truth_scrub(
            message,
            reply,
            factual_packet=factual_packet,
            action_type=action_type,
            _tb=_tb,
        )
        reply = ensure_nonempty_reply(reply)
    except Exception:
        pass
    try:
        from services.memory.self_change import maybe_prepend_boot_change_announce

        reply, factual_packet = maybe_prepend_boot_change_announce(
            owner_message=message,
            reply=reply,
            factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
            action_type=action_type,
        )
        reply = ensure_nonempty_reply(reply)
    except Exception:
        pass

    # Proactive workflow chaining:
    if isinstance(factual_packet, dict) and factual_packet.get("status") == "ok" and not require_confirmation:
        tool = factual_packet.get("tool")
        cid = factual_packet.get("capsule_id") or capsule_id
        if cid is not None:
            try:
                cid = int(cid)
            except (ValueError, TypeError):
                cid = None

        if cid is not None:
            next_action = None
            next_prompt = None
            if tool in ("approve_capsule", "approve_latest_script"):
                next_action = "generate_audio"
                next_prompt = "\n\nKya main ab iska audio generate karoon? (Haan/Nahi)"
            elif tool in ("generate_audio", "prepare_capsule_audio"):
                next_action = "send_azuracast"
                next_prompt = "\n\nKya main ise AzuraCast par upload karoon? (Haan/Nahi)"
            elif tool == "send_azuracast":
                next_action = "assign_capsule_to_playlist"
                next_prompt = "\n\nKya main ise schedule playlist par lagaoon? (Haan/Nahi)"

            if next_action and next_prompt:
                manager_state.set_pending_action(
                    action_type=next_action,
                    category="live_ops",
                    risk_level="high",
                    protected=True,
                    executable_now=True,
                    requires_stage="owner_confirmation",
                    status="pending_owner_confirmation",
                    expires_after_turns=1,
                    payload={
                        "resume_action": next_action,
                        "resume_slots": {"capsule_id": cid},
                        "capsule_id": cid,
                    },
                )
                if next_prompt not in reply:
                    reply += next_prompt
    if _tb is not None and job_id:
        try:
            _tb.job_id = job_id
        except Exception:
            pass
    manager_state.record_turn(action_type, getattr(_tb, "route", None) if _tb is not None else None, message)
    try:
        from services.memory.continuity import commit_owner_turn

        commit_owner_turn(
            message,
            reply,
            action_type=action_type,
            route=getattr(_tb, "route", None) if _tb is not None else None,
            tb=_tb,
            require_confirmation=bool(require_confirmation),
            job_id=job_id,
            factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
        )
    except Exception:
        memory_adapter.save_chat_turn("user", message)
        memory_adapter.save_chat_turn("model", reply)
        try:
            from services.agent.working_context import update_working_context_after_turn

            update_working_context_after_turn(
                message=message,
                reply=reply,
                action_type=action_type,
                route=getattr(_tb, "route", None) if _tb is not None else None,
                tb=_tb,
                require_confirmation=bool(require_confirmation),
                job_id=job_id,
                factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
            )
        except Exception:
            pass
    result = {
        "reply": reply,
        "command_triggered": command_triggered,
        "require_confirmation": require_confirmation,
        "action_type": action_type,
    }
    if isinstance(factual_packet, dict):
        result["factual_packet"] = factual_packet
    if job_id is not None:
        result["job_id"] = job_id
    if approval_id is not None:
        result["approval_id"] = approval_id
    if capsule_id is not None:
        result["capsule_id"] = capsule_id
    if approval_status is not None:
        result["approval_status"] = approval_status
    if audio_truth_level is not None:
        result["audio_truth_level"] = audio_truth_level
    if azuracast_status is not None:
        result["azuracast_status"] = azuracast_status
    if _tb is not None:
        if _tb.memory_save_status is None:
            _tb.memory_save_status = "not_attempted"
        result.update(_tb.build())
    return result


def _smart_conversational_reply(
    message: str,
    mem_packet: dict | None,
    mem_context: str | None,
    tb: "_TraceBuilder",
    *,
    live_snapshot: dict | None = None,
    reason: str = "conversation",
    action_type: str = "CONVERSATION",
) -> dict | None:
    """Generate a natural grounded LLM reply. Returns None if LLM unavailable."""
    from services.brain.conversation import generate_conversational_reply

    reply = generate_conversational_reply(
        message,
        mem_packet=mem_packet,
        mem_context=mem_context,
        live_snapshot=live_snapshot,
        tb=tb,
        reason=reason,
    )
    if not reply:
        return None
    return _save_and_return(message, reply, action_type=action_type, _tb=tb)


def _apply_memory_packet_trace(tb: "_TraceBuilder", mem_packet: dict) -> None:
    tb.memory_mode = mem_packet.get("memory_mode") or tb.memory_mode
    tb.memory_search_used = mem_packet.get("memory_search_used") or tb.memory_search_used
    tb.memory_hits_count = int(mem_packet.get("memory_hits_count") or 0)
    tb.embedding_model_used = mem_packet.get("embedding_model_used")
    tb.memory_backend = mem_packet.get("memory_backend")
    tb.semantic_memory_used = bool(mem_packet.get("semantic_memory_used"))
    tb.memory_fallback_reason = mem_packet.get("memory_fallback_reason")
    tb.short_context_used = "Yes"


def _is_diagnostics_fast_message(msg_lower: str) -> bool:
    """Exact diagnostics strings only (AGENTS allowed) — no phrase NLU."""
    return msg_lower in {
        "diagnostics kro",
        "diagnostics run karo",
        "run diagnostics",
        "diagnostics",
    }


def _run_diagnostics_fast_path(message: str, tb: "_TraceBuilder") -> dict | None:
    if not _is_diagnostics_fast_message((message or "").lower().strip()):
        return None
    tb.source = "local_tool"
    tb.route = "diagnostics"
    tb.memory_mode = "short_term_only"
    tb.memory_search_used = "short_term_only"
    tb.memory_hits_count = 0
    tb.embedding_model_used = None
    tb.memory_backend = None
    tb.semantic_memory_used = False
    tb.memory_fallback_reason = "skipped_temporary_request"
    tb.memory_save_status = "not_attempted"
    tb.short_context_used = "No"
    tb.whatsapp_gateway = rc.get_whatsapp_gateway_trace_status()
    tb.step("tool_call", "Running read-only diagnostics (fast path)")
    tb.mark("tools")
    allowed, reply = run_diagnostics_command()
    tb.tool_suggested = "diagnostics"
    tb.tool_executed = "true" if allowed else "false"
    tb.tool_result_present = "true" if allowed else "false"
    tb.executed_tool_name = "diagnostics" if allowed else "null"
    tb.local_tool_executed = "diagnostics" if allowed else "None"
    tb.step("response", "Diagnostics report prepared")
    return _save_and_return(
        message,
        reply,
        command_triggered="RUN_DIAGNOSTICS" if allowed else None,
        action_type="RUN_DIAGNOSTICS" if allowed else "blocked",
        _tb=tb,
    )


def _apply_session_trace(
    tb: "_TraceBuilder",
    *,
    pending_candidate_active: bool | None = None,
    approval_consumed: bool | None = None,
) -> None:
    trace = manager_state.get_session_trace_info()
    tb.session_backend = trace.get("session_backend")
    tb.redis_available = trace.get("redis_available")
    tb.pending_state_source = trace.get("pending_state_source")
    tb.redis_fallback_reason = trace.get("redis_fallback_reason")
    if pending_candidate_active is None:
        tb.pending_candidate_active = memory_service.get_pending_permanent_memory_candidate() is not None
    else:
        tb.pending_candidate_active = pending_candidate_active
    if approval_consumed is not None:
        tb.approval_consumed = "Yes" if approval_consumed else "No"



# format_whatsapp_status_reply moved to neena_tool_executor.py

def _execute_station_command(message: str, command_type: str, success_reply: str, _tb: "_TraceBuilder | None" = None) -> dict:
    command_id = db.add_station_command(command_type)
    result = rc.execute_station_command(command_id, command_type)
    if result.get("success"):
        reply = success_reply
    else:
        reply = f"Command execute failed: {result.get('message', 'unknown error')}"
    return _save_and_return(message, reply, command_triggered=command_type, action_type=command_type, _tb=_tb)

# run_diagnostics_command moved to neena_tool_executor.py

def get_station_context() -> str:
    """
    Delegates to modular context builder.
    """
    return context_builder.build_context_block()

LLM_UNAVAILABLE_SENTINEL = "__LLM_UNAVAILABLE__"

def _is_llm_unavailable(reply: str) -> bool:
    """Returns True if the reply text indicates LLM/Gemini was unreachable."""
    lower = reply.lower()
    return (
        "network connection issue" in lower
        or "google gemini api" in lower
        or "gemini api returned code" in lower
        or "gemini api key is missing" in lower
        or "llm connect nahi ho raha" in lower
        or "selected model unavailable" in lower
        or ("error" in lower and "api" in lower)
    )

def _llm_unavailable_reply() -> str:
    """Short, honest LLM unavailable reply — no long error details."""
    return (
        "LLM connect nahi ho raha, creative kaam abhi blocked hai. "
        "Fake/template content nahi banaungi. "
        "Monitoring, source tools aur approval/control commands chal sakte hain."
    )




def _handle_approval_queue_and_preview_command(msg_lower: str) -> str:
    """Deterministic handler for approval and preview generation without calling LLM."""
    import re
    id_match = re.search(r'\bid\s*(\d+)\b|\bapproval_id\s*(\d+)\b|\bapprove\s*(\d+)\b', msg_lower)
    target_id = None
    if id_match:
        target_id = int(id_match.group(1) or id_match.group(2) or id_match.group(3))

    try:
        if target_id is not None:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approval_queue WHERE id = ?", (target_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return f"Script ID {target_id} not found in approval queue."
            item = dict(row)
        else:
            pending = db.get_pending_approvals(limit=10)
            if not pending:
                return "Approval queue empty — no pending scripts."
            if len(pending) > 1:
                ids_str = ", ".join(str(p["id"]) for p in pending)
                return (
                    f"Multiple pending scripts in approval queue (IDs: {ids_str}). "
                    "Specify which ID to approve."
                )
            item = pending[0]

        # Process approval status update
        db.update_approval_status(item["id"], "approved")
        try:
            from services.broadcast.capsule_service import update_capsule_approval_status
            update_capsule_approval_status(item["id"], "approved")
        except Exception:
            pass
        db.add_activity_log("approval", f"Approved script ID {item['id']} via owner command")

        # Get active voice persona
        voice_id = "21m00Tcm4TlvDq8ikWAM"  # default voice
        try:
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT elevenlabs_voice_id FROM voice_personas WHERE id = 'rj_neena' AND active = 1")
            v_row = cursor.fetchone()
            conn.close()
            if v_row and v_row["elevenlabs_voice_id"]:
                voice_id = v_row["elevenlabs_voice_id"]
        except Exception:
            pass

        from services.voice.gen_service import render_approved_script
        from services.voice.generator import get_elevenlabs_key

        api_key = get_elevenlabs_key()
        is_real = api_key and "here" not in api_key.lower() and "placeholder" not in api_key.lower()

        filepath = render_approved_script(
            script_id=item["id"],
            voice_id=voice_id,
            text=item.get("content_data", "")
        )

        if is_real:
            return (
                f"Script ID {item['id']} approved; real ElevenLabs voice preview generated."
            )
        return (
            f"Script ID {item['id']} approved; voice provider key missing — "
            "preview labeled simulated/unavailable."
        )
    except Exception as e:
        logger.error(f"Error handling approval/preview command: {e}")
        return f"Approval/preview command failed: {str(e)}"


def _handle_pre_intent_guards(message: str, msg_lower: str, tb: "_TraceBuilder") -> dict | None:
    """Pre-intent guard stage (SRP): owner approval + permanent-memory candidates.

    Runs BEFORE any intent routing. Returns a finished result dict to short-circuit
    the pipeline, or None to continue to memory/intent dispatch. Covers:
      * permanent-memory candidate confirm / cancel / new request
      * frictionless one-tap confirmation of a surfaced protected action
      * a bare approval ("haan") with no active pending action -> clarify
    """
    pending_memory_candidate = memory_service.get_pending_permanent_memory_candidate()
    if pending_memory_candidate and not memory_service.is_memory_rejection_message(msg_lower) and (is_confirmation_only(msg_lower) or msg_lower == "approved" or is_affirmative_reply(msg_lower)):
        tb.source = "local_router"
        tb.route = "permanent_memory_confirmation"
        tb.reached_interpreter = False
        tb.short_circuit_reason = "permanent_memory_confirm"
        tb.blink("memory_confirm", status="accepted")
        tb.step("memory", "Owner confirmed pending permanent memory candidate")
        memory_res = memory_service.confirm_pending_permanent_memory_candidate(message)
        tb.memory_mode = "short_term_plus_permanent_text"
        tb.memory_save_status = memory_res.get("memory_save_status")
        tb.memory_write_backend = memory_res.get("memory_write_backend")
        tb.postgres_write_status = memory_res.get("postgres_write_status")
        tb.postgres_embedding_status = memory_res.get("postgres_embedding_status")
        tb.postgres_memory_id = memory_res.get("postgres_memory_id")
        tb.sqlite_mirror_status = memory_res.get("sqlite_mirror_status")
        tb.sqlite_memory_id = memory_res.get("sqlite_memory_id")
        tb.local_tool_executed = "save_permanent_memory" if memory_res.get("status") == "saved" else "None"
        _apply_session_trace(tb, pending_candidate_active=False, approval_consumed=memory_res.get("status") == "saved")
        tb.step("response", "Permanent memory confirmation handled")
        return _save_and_return(message, memory_res["reply"], action_type="PERMANENT_MEMORY_SAVE", factual_packet=memory_res.get("factual_packet") if isinstance(memory_res.get("factual_packet"), dict) else None, _tb=tb)

    if pending_memory_candidate and memory_service.is_memory_rejection_message(msg_lower):
        tb.source = "local_router"
        tb.route = "permanent_memory_cancel"
        tb.step("memory", "Owner cancelled pending permanent memory candidate")
        memory_res = memory_service.cancel_pending_permanent_memory_candidate()
        tb.memory_mode = "short_term_plus_permanent_text"
        tb.memory_save_status = memory_res.get("memory_save_status")
        _apply_session_trace(tb, pending_candidate_active=False, approval_consumed=False)
        tb.step("response", "Permanent memory candidate cancelled")
        return _save_and_return(
            message,
            memory_res["reply"],
            action_type="PERMANENT_MEMORY_CANCEL",
            factual_packet=memory_res.get("factual_packet") if isinstance(memory_res.get("factual_packet"), dict) else None,
            _tb=tb,
        )

    edit_res = memory_edit_service.try_confirm_or_cancel(msg_lower, message, tb, _save_and_return)
    if edit_res is not None:
        return edit_res

    # Permanent-memory / remember: interpreter → propose_permanent_memory (no phrase NLU).

    pending_action_for_local_approval = manager_state.get_pending_action()

    # Frictionless one-tap confirmation for a surfaced protected action:
    # existing affirmative helper (same as memory confirm) executes it;
    # "nahi / cancel" drops it; any other new command invalidates the stale pending.
    if (
        pending_action_for_local_approval
        and pending_action_for_local_approval.get("protected")
        and pending_action_for_local_approval.get("action_type") in _ONE_TAP_PROTECTED_ACTIONS
    ):
        _resume = pending_action_for_local_approval.get("payload") or {}
        _resume_action = _resume.get("resume_action") or pending_action_for_local_approval.get("action_type")
        tb.pending_action_snapshot = {
            "action_type": pending_action_for_local_approval.get("action_type"),
            "protected": True,
            "resume_action": _resume_action,
            "capsule_id": _resume.get("capsule_id") or (_resume.get("resume_slots") or {}).get("capsule_id"),
            "status": pending_action_for_local_approval.get("status"),
        }
        tb.blink("pending_seen", action=_resume_action, capsule_id=tb.pending_action_snapshot.get("capsule_id"))
        if any(p in msg_lower for p in _ONE_TAP_CANCEL_PHRASES):
            manager_state.clear_pending_action()
            tb.source = "local_router"
            tb.route = "confirmation_cancelled"
            tb.reached_interpreter = False
            tb.short_circuit_reason = "one_tap_cancelled"
            tb.blink("confirm_rejected", reason="cancel")
            tb.step("response", f"Owner cancelled pending protected action: {_resume_action}")
            _apply_session_trace(tb, pending_candidate_active=False, approval_consumed=False)
            return _save_and_return(
                message,
                f"Pending protected action cancelled: {_resume_action}.",
                action_type="confirmation_cancelled",
                factual_packet={
                    "tool": "confirmation_cancelled",
                    "status": "ok",
                    "cancelled_action": _resume_action,
                },
                _tb=tb,
            )
        if is_confirmation_only(msg_lower) or msg_lower == "approved" or is_affirmative_reply(msg_lower):
            _resume_slots = dict(_resume.get("resume_slots") or {})
            _resume_slots.update({"explicit_push": True, "explicit_approval": True})
            bound_cid = _resume.get("capsule_id") or _resume_slots.get("capsule_id")
            if bound_cid is not None:
                _resume_slots["capsule_id"] = bound_cid
            manager_state.clear_pending_action()
            from services.tools.live_ops_executor import try_execute_live_ops
            op_result = try_execute_live_ops(_resume_action, _resume_slots, owner_message="confirm karo")
            if op_result:
                tb.source = "live_ops"
                tb.route = f"confirmed_{_resume_action}"
                tb.reached_interpreter = False
                tb.short_circuit_reason = "one_tap_confirm_accepted"
                tb.capsule_id_resolved = op_result.get("capsule_id") or bound_cid
                tb.blink("confirm_accepted", action=_resume_action, capsule_id=tb.capsule_id_resolved)
                tb.step("tool_call", f"One-tap confirmation executed pending {_resume_action}")
                _apply_session_trace(tb, pending_candidate_active=False, approval_consumed=True)
                result = _save_and_return(
                    message,
                    op_result.get("reply", "Done."),
                    action_type=op_result.get("action_type"),
                    capsule_id=op_result.get("capsule_id") or bound_cid,
                    require_confirmation=bool(op_result.get("require_confirmation")),
                    factual_packet=op_result.get("factual_packet"),
                    _tb=tb,
                )
                for _k in ("ui_action", "job_id", "approval_id"):
                    if op_result.get(_k) is not None:
                        result[_k] = op_result[_k]
                return result
        else:
            # Owner moved on to a different command — drop the stale pending.
            manager_state.clear_pending_action()
            tb.pending_cleared_without_execute = True
            tb.blink("pending_cleared", reason="non_affirmative_new_command", action=_resume_action)
            # Do not return — continue so interpreter/model can handle the new command.

    if not pending_action_for_local_approval and (is_confirmation_only(msg_lower) or msg_lower == "approved"):
        tb.source = "local_router"
        tb.route = "clarify_approval"
        tb.policy_decision = "clarify_approval"
        tb.approval_blocked_reason = "no_active_pending_action"
        tb.reached_interpreter = False
        tb.short_circuit_reason = "confirm_without_pending"
        tb.step("response", "Approval-only message received with no active pending action")
        _apply_session_trace(tb, pending_candidate_active=False, approval_consumed=False)
        return _save_and_return(
            message,
            "No active pending action to approve. Specify which action.",
            action_type="clarification",
            factual_packet={
                "tool": "clarify_approval",
                "status": "no_pending",
                "reason": "confirm_without_pending",
            },
            _tb=tb,
        )

    return None


def _should_skip_embedding_recall(msg_lower: str) -> bool:
    from services.llm.intent_router import is_confirmation_only, is_affirmative_reply
    if is_confirmation_only(msg_lower) or is_affirmative_reply(msg_lower):
        return True

    _SKIP_WORDS = {
        "hi", "hello", "hey", "hii", "hello neena", "helo", "bye", "ok", "okay", "cancel", "stop",
        "rehne do", "nahi", "no", "yes", "haan", "yo", "sup", "namaste", "namaskar", "kese ho", "kaise ho",
        "tum kaise ho", "thank you", "thanks", "shukriya", "dhanyawad", "dhanyavad", "aur batao", "aur batayo"
    }
    cleaned = msg_lower.strip().strip(".!,?").strip()
    if cleaned in _SKIP_WORDS:
        return True

    words = cleaned.split()
    if len(words) <= 2:
        system_keywords = {
            "status", "diagnose", "diagnostics", "script", "capsule", "audio", "playlist", "azura",
            "azuracast", "stream", "listener", "memory", "remember", "intention", "lock", "unlock", "play"
        }
        if not any(kw in cleaned for kw in system_keywords):
            return True

    return False


def _is_simple_conversational_only(msg_lower: str) -> bool:
    _CASUAL_WORDS = {
        "hi", "hello", "hey", "hii", "hello neena", "helo", "yo", "sup", "namaste", "namaskar",
        "kaise ho", "kese ho", "tum kaise ho", "kem cho", "good morning", "good afternoon", "good evening",
        "thank you", "thanks", "shukriya", "dhanyawad", "dhanyavad", "aur batao", "aur batayo"
    }
    cleaned = msg_lower.strip().strip(".!,?").strip()
    return cleaned in _CASUAL_WORDS


def process_owner_message(
    message: str,
    selected_model: str = "auto",
    *,
    channel: str = "command_center",
) -> dict:
    """
    Parses owner messages, delegates routing and compose tasks, and returns Hinglish responses.
    """
    from services.brain.self_knowledge import inbound_channel_scope

    with inbound_channel_scope(channel):
        return _process_owner_message_inner(message, selected_model=selected_model)


def _process_owner_message_inner(message: str, selected_model: str = "auto") -> dict:
    """
    Parses owner messages, delegates routing and compose tasks, and returns Hinglish responses.
    """
    tb = _TraceBuilder()
    tb.selected_model = selected_model
    msg_lower = message.lower().strip()
    command_triggered = None
    require_confirmation = False
    action_type = None
    policy_res = None
    packet = None
    routed = None

    # Track model call count variables
    intent_model_call_count = 0
    response_model_call_count = 0
    model_unavailable_reason = None
    fallback_model_used = False

    tb.step("received", "Owner command received")

    # Stage: pre-intent guards (owner approval + permanent-memory candidates).
    guard_result = _handle_pre_intent_guards(message, msg_lower, tb)
    if guard_result is not None:
        return guard_result

    tb.whatsapp_gateway = rc.get_whatsapp_gateway_trace_status()

    # Self / future / day notebook: interpreter → catalog tools (memory_notebook.py).
    # No regex phrase short-circuits here (AGENTS hygiene).

    # One-brain: recall via facade (soft-fade + strengthen-on-use). Legacy packet kept for traces.
    if _should_skip_embedding_recall(msg_lower):
        mem_packet = {"hits": [], "context_text": ""}
        mem_context = ""
    elif feature_flags.one_brain_foundation_enabled():
        from services.memory.facade import recall as memory_recall

        _facade = memory_recall(role="owner", subject_key="owner", query=message, limit=8)
        mem_packet = _facade.get("legacy_packet") or memory_service.get_memory_context_packet(message)
        # Prefer facade-ranked hits when present
        if _facade.get("hits"):
            mem_packet = dict(mem_packet)
            mem_packet["hits"] = _facade.get("hits")
            if _facade.get("context_text"):
                mem_packet["context_text"] = _facade.get("context_text")
        mem_context = mem_packet.get("context_text") or memory_service.build_memory_context(message)
    else:
        mem_packet = memory_service.get_memory_context_packet(message)
        mem_context = mem_packet.get("context_text") or memory_service.build_memory_context(message)
    tb.step("memory", "Memory context constructed")
    _apply_memory_packet_trace(tb, mem_packet)
    tb.memory_save_status = "not_attempted"
    local_memory_answer = None

    # Exact diagnostics strings only (AGENTS allowed). All other intents → interpreter.
    diag = _run_diagnostics_fast_path(message, tb)
    if diag is not None:
        return diag

    if contains_forbidden_command(msg_lower):
        tb.source = "local_router"
        tb.route = "blocked"
        tb.reached_interpreter = False
        tb.short_circuit_reason = "forbidden_command"
        tb.step("response", "Forbidden command pattern detected — blocked")
        return _save_and_return(
            message,
            "Arbitrary/destructive command blocked. Only predefined safe tools or approved backend actions are allowed.",
            action_type="blocked",
            factual_packet={"tool": "forbidden_command", "status": "blocked"},
            _tb=tb,
        )

    # Natural language: interpreter → structured executor (no phrase twin router).
    # M4-A8.5.2 — Natural language: model interpreter → structured executor only
    from services.brain.command_interpreter import (
        LOW_CONFIDENCE_THRESHOLD,
        build_interpreter_timeout_reply,
        interpret_owner_command,
    )

    tb.step("routing", "Natural language — command interpreter (max 1 model call)")

    if not pr.is_llm_configured():
        from services.llm.model_status import build_model_status_reply

        tb.source = "local_fallback"
        tb.route = "blocked"
        tb.llm_status = "unavailable"
        reply = build_model_status_reply()
        return _save_and_return(message, reply, action_type="MODEL_STATUS", _tb=tb)

    # Customer WhatsApp recall: interpreter → catalog tool
    # customer_whatsapp_recall (no phrase/regex NLU short-circuit).

    from services.brain.live_state_snapshot import (
        build_neena_live_state_snapshot,
        format_snapshot_for_interpreter,
    )

    live_snapshot = build_neena_live_state_snapshot()
    try:
        from services.memory.continuity import build_owner_prompt_context
        from services.agent.system_knowledge_pack import system_knowledge_pack_text

        prompt_ctx = build_owner_prompt_context(message)
        _wc = prompt_ctx.get("working_block") or ""
        _sk = system_knowledge_pack_text()
        _extra = ""
        if _sk:
            _extra += "\n\n" + _sk
        if _wc:
            _extra += "\n\n" + _wc
        _short = prompt_ctx.get("short_context") or ""
        if _short and _short not in (mem_context or ""):
            _extra += "\n\n" + _short
        if _extra:
            mem_context = (mem_context or "") + _extra
    except Exception:
        pass
    mem_context = (
        (mem_context or "")
        + "\n\nLIVE COMMAND CENTER STATE:\n"
        + format_snapshot_for_interpreter(live_snapshot)
    )
    tb.step("live_state", "NEENA_LIVE_STATE_SNAPSHOT attached for interpreter")
    _routing_t0 = time.monotonic()
    if _is_simple_conversational_only(msg_lower):
        interp_packet = {
            "action": "unknown",
            "confidence": 0.0,
            "owner_facing_summary": "Casual chat greeting"
        }
        provider = "local"
        status_str = "available"
        resolved_model_id = "local-bypass"
    else:
        interp_packet, provider, status_str, resolved_model_id = interpret_owner_command(
            message, memory_context=mem_context
        )
    tb.reached_interpreter = True
    tb.reached_model = provider != "local" and status_str == "available"
    tb.short_circuit_reason = None
    tb.blink(
        "interpreter_invoked",
        provider=provider,
        status=status_str,
        model=resolved_model_id,
    )
    tb._checkpoints["routing"] = round((time.monotonic() - _routing_t0) * 1000)
    intent_model_call_count = 0 if provider == "local" else (1 if status_str == "available" else 0)
    tb.llm_provider = provider
    tb.llm_status = status_str
    tb.actual_model = resolved_model_id
    tb.actual_api_model_id = resolved_model_id
    tb.intent_model_call_count = intent_model_call_count

    action = (interp_packet.get("action") or "unknown").strip().lower()
    slots_reason = (interp_packet.get("slots") or {}).get("reason")
    _slots = dict(interp_packet.get("slots") or {})
    # Cooldown/unavailable packets must not look like an intentional model_status ask.
    if action == "model_status" and slots_reason in (
        "cooldown",
        "rate_limited",
        "interpreter_timeout",
        "no_api_key",
        "model_unavailable",
        "provider_error",
    ):
        action = "unknown"
    # Safe packet summary for recorder (no prompts / secrets)
    _slot_keys = ("capsule_id", "approval_id", "explicit_push", "explicit_approval", "reason")
    tb.action_packet_summary = {
        "action": action,
        "confidence": interp_packet.get("confidence"),
        "slots": {k: _slots[k] for k in _slot_keys if k in _slots},
        "source": interp_packet.get("source") or provider,
    }
    if _slots.get("capsule_id") is not None:
        tb.capsule_id_resolved = _slots.get("capsule_id")

    if status_str == "timeout" or slots_reason == "interpreter_timeout":
        tb.source = "local_router"
        tb.route = "interpreter_timeout_model_status"
        reply = build_interpreter_timeout_reply(live_snapshot)
        return _save_and_return(message, reply, action_type="MODEL_STATUS", _tb=tb)

    # Cooldown / provider gap: prefer honest conversation over model-status dump
    # when we never got a real action classification.
    if status_str in ("cooldown", "rate_limited", "unavailable", "provider_error", "model_unavailable") and action == "unknown":
        wait = pr.peek_cooldown_wait(resolved_model_id or "")
        pr.apply_model_limit_trace(tb, model_call_status=status_str, wait_seconds=wait)
        smart = _smart_conversational_reply(
            message,
            mem_packet,
            mem_context,
            tb,
            live_snapshot=live_snapshot,
            reason=f"interpreter_{status_str}",
            action_type="CONVERSATION",
        )
        if smart is not None:
            return smart
        from services.llm.model_status import build_model_status_reply

        reply = build_model_status_reply(live_snapshot)
        return _save_and_return(message, reply, action_type="MODEL_STATUS", _tb=tb)

    # Cooldown harden: local/deterministic actions still run when classified.
    _LOCAL_OK_ON_COOLDOWN = frozenset(
        {
            "manage_memory",
            "propose_permanent_memory",
            "station_status",
            "diagnostics",
            "time_status",
            "pipeline_status",
            "list_pending_capsules",
            "capsule_status",
            "open_latest_capsule",
            "check_interaction_recorder",
            "what_should_i_do_now",
            "verify_stream",
            "ensure_playback",
            "memory_status",
            "now_playing",
            "get_station_schedule",
            "whats_next",
            "day_memory_recall",
            "future_intention_save",
            "future_intention_recall",
            "future_intention_lifecycle",
            "self_profile",
            "self_life_story",
            "self_architecture",
            "customer_whatsapp_recall",
        }
    )
    _rate_limited = pr.is_model_rate_limited_status(status_str)
    if action == "model_status" or (
        _rate_limited and action not in _LOCAL_OK_ON_COOLDOWN
    ) or (status_str != "available" and action not in _LOCAL_OK_ON_COOLDOWN):
        wait = pr.peek_cooldown_wait(resolved_model_id or "")
        pr.apply_model_limit_trace(tb, model_call_status=status_str, wait_seconds=wait)
        from services.llm.model_status import build_model_status_reply

        reply = build_model_status_reply(live_snapshot)
        return _save_and_return(message, reply, action_type="MODEL_STATUS", _tb=tb)

    confidence = float(interp_packet.get("confidence") or 0.0)

    if (pref_result := owner_preferences.try_handle_interpreter_action(
        action, interp_packet, live_snapshot, message, tb, _save_and_return
    )) is not None:
        return pref_result

    if action == "unknown" or confidence < LOW_CONFIDENCE_THRESHOLD:
        smart = _smart_conversational_reply(
            message,
            mem_packet,
            mem_context,
            tb,
            live_snapshot=live_snapshot,
            reason="low_confidence_or_unknown",
        )
        if smart is not None:
            return smart
        reply = (
            interp_packet.get("owner_facing_summary")
            or "Clarify needed: status, diagnostics, RJ intro, or ad script?"
        )
        tb.source = "local_router"
        tb.route = "clarification"
        tb.final_reply_source = "command_interpreter"
        return _save_and_return(message, reply, action_type="clarification", _tb=tb)

    op_result = None
    try:
        from services.agent.run_kernel import run_owner_kernel, should_enter_kernel

        if should_enter_kernel(action, message):
            op_result = run_owner_kernel(
                message=message,
                interpreter_packet=interp_packet,
                selected_model=selected_model,
                mem_packet=mem_packet,
                mem_context=mem_context,
                tb=tb,
                live_snapshot=live_snapshot,
            )
    except Exception:
        op_result = None

    if op_result is None:
        op_result = operations_workflows.try_handle_interpreter_packet(
            message=message,
            interpreter_packet=interp_packet,
            selected_model=selected_model,
            mem_packet=mem_packet,
            mem_context=mem_context,
            tb=tb,
        )
        if op_result is not None:
            try:
                from services.tools.loop import extend_live_ops_result

                op_result = extend_live_ops_result(
                    message=message,
                    first_result=op_result,
                    first_action=action,
                    tb=tb,
                )
            except Exception:
                pass

    if op_result is not None:
        op_tb = op_result.pop("_tb", tb)
        extra_keys = (
            "ui_action",
            "job_id",
            "mode",
            "live_snapshot",
            "script_preview",
            "require_confirmation",
            "latency_ms",
            "gemini_calls",
        )
        result = _save_and_return(
            message,
            op_result["reply"],
            action_type=op_result.get("action_type"),
            command_triggered=op_result.get("command_triggered"),
            approval_id=op_result.get("approval_id"),
            capsule_id=op_result.get("capsule_id"),
            approval_status=op_result.get("approval_status"),
            audio_truth_level=op_result.get("audio_truth_level"),
            azuracast_status=op_result.get("azuracast_status"),
            require_confirmation=bool(op_result.get("require_confirmation")),
            factual_packet=op_result.get("factual_packet"),
            job_id=op_result.get("job_id"),
            _tb=op_tb,
        )
        for key in extra_keys:
            if op_result.get(key) is not None:
                result[key] = op_result[key]
        # Remember a surfaced protected action so a plain "haan" next turn
        # executes it (frictionless one-tap approval).
        if op_result.get("require_confirmation") and action in _ONE_TAP_PROTECTED_ACTIONS:
            _resume_slots = dict(interp_packet.get("slots") or {})
            _bound_cid = op_result.get("capsule_id")
            if _bound_cid is not None:
                _resume_slots["capsule_id"] = _bound_cid
            tb.capsule_id_resolved = _bound_cid or _resume_slots.get("capsule_id")
            tb.blink(
                "pending_set",
                action=action,
                capsule_id=tb.capsule_id_resolved,
            )
            manager_state.set_pending_action(
                action_type=action,
                category="live_ops",
                risk_level="high",
                protected=True,
                executable_now=True,
                requires_stage="owner_confirmation",
                status="pending_owner_confirmation",
                expires_after_turns=1,
                payload={
                    "resume_action": action,
                    "resume_slots": _resume_slots,
                    "capsule_id": _bound_cid,
                },
            )
        elif (
            op_result.get("require_confirmation")
            and op_result.get("pending_fix_action") == "fix_app_listener_path"
        ):
            manager_state.set_pending_action(
                action_type="fix_app_listener_path",
                category="live_ops",
                risk_level="high",
                protected=True,
                executable_now=True,
                requires_stage="owner_confirmation",
                status="pending_owner_confirmation",
                expires_after_turns=1,
                payload={
                    "resume_action": "fix_app_listener_path",
                    "resume_slots": dict(op_result.get("pending_fix_slots") or {}),
                },
            )
        result["live_snapshot_summary"] = live_snapshot.get("recommended_next_action")
        return result

    smart = _smart_conversational_reply(
        message,
        mem_packet,
        mem_context,
        tb,
        live_snapshot=live_snapshot,
        reason="unsupported_action",
    )
    if smart is not None:
        return smart
    reply = (
        interp_packet.get("owner_facing_summary")
        or "Action not supported this turn."
    )
    return _save_and_return(
        message,
        reply,
        action_type="unsupported",
        factual_packet={
            "tool": "unsupported_action",
            "status": "unsupported",
            "action": (interp_packet.get("action") or "unknown"),
        },
        _tb=tb,
    )

    # NOTE (M6 Phase 4): the former "Stage C legacy creative LLM path" lived here
    # but was proven UNREACHABLE — both the exact-command branch and the NL
    # interpreter branch above always return. Removed as dead code; creative
    # generation now flows through neena_operations_workflows via the interpreter.
    # See tests/test_neena_brain_pipeline.py::TestLegacyCreativeTailUnreachable.


# ---------------------------------------------------------------------------
# SINGLE BRAIN ENTRY — owner / customer / employee (ADR-008)
# ---------------------------------------------------------------------------
ActorRole = Literal["owner", "customer", "employee"]


def process_message(
    *,
    role: ActorRole | str = "customer",
    message: str,
    selected_model: str = "auto",
    sender_name: str = "ji",
    phone: str = "",
    channel: str = "command_center",
) -> dict[str, Any]:
    """Unified single brain entry delegating execution to BOS Runtime Engine."""
    from backend.runtime.engine import BOSRuntimeEngine

    return BOSRuntimeEngine.execute(
        role=role,
        message=message,
        selected_model=selected_model,
        sender_name=sender_name,
        phone=phone,
        channel=channel,
    )


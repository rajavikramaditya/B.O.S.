"""Owner Run Kernel — goal→plan→inventory→act→verify (ADR-012).

Wraps existing interpreter + catalog + live_ops/cockpit + tool loop.
Does not invent a second executor. Neena remains a separate agent product;
Azura/CC are managed targets via tools.
"""
from __future__ import annotations

import logging
from typing import Any

from services.agent.run_contract import OwnerRun, new_run
from services.agent.truth_gate import (
    build_cannot_packet,
    build_cannot_reply,
    is_work_action,
    unavailable_action_reason,
)

logger = logging.getLogger(__name__)

# Actions that are chat / not kernel work.
_SKIP_KERNEL = frozenset(
    {
        "unknown",
        "conversation",
        "chat",
        "clarify",
        "clarification",
        "set_response_style",
        "propose_permanent_memory",
        "manage_memory",
    }
)

# Seed plans: action → ordered tool ids (first = primary).
_RECIPES: dict[str, list[str]] = {
    "now_playing": ["now_playing"],
    "whats_next": ["whats_next", "now_playing"],
    "get_station_schedule": ["get_station_schedule", "now_playing"],
    "assign_capsule_to_playlist": ["assign_capsule_to_playlist", "get_station_schedule"],
    "station_status": ["station_status", "now_playing"],
    "vm_status": ["vm_status"],
    "verify_stream": ["verify_stream"],
    "ensure_playback": ["ensure_playback", "verify_stream"],
    "capsule_status": ["capsule_status"],
    "diagnostics": ["diagnostics"],
    "pipeline_status": ["pipeline_status"],
    "what_should_i_do_now": ["what_should_i_do_now", "now_playing"],
    "send_azuracast": ["send_azuracast", "verify_stream"],
    "generate_audio": ["generate_audio"],
    "capabilities": ["capabilities"],
    "time_status": ["time_status"],
    "memory_status": ["memory_status"],
    "model_status": ["model_status"],
    "arm_deferred_status": ["arm_deferred_status"],
    "customer_whatsapp_recall": ["customer_whatsapp_recall"],
    "day_memory_recall": ["day_memory_recall"],
    "create_station_plan": ["create_station_plan"],
    "get_station_plan": ["get_station_plan"],
    "advance_station_plan": ["advance_station_plan"],
    "draft_plan_block": ["draft_plan_block"],
}


def _catalog_ids() -> set[str]:
    try:
        from services.tools.catalog import action_ids

        return set(action_ids())
    except Exception:
        return set()


def should_enter_kernel(action: str | None, message: str = "") -> bool:
    if unavailable_action_reason(message):
        return True  # kernel/truth path for cannot
    a = (action or "").strip().lower()
    if a in _SKIP_KERNEL or not is_work_action(a):
        return False
    return True


def _plan_for(action: str) -> list[str]:
    steps = list(_RECIPES.get(action) or [action])
    out: list[str] = []
    for s in steps:
        if s and s not in out:
            out.append(s)
    return out


def _inventory(plan: list[str]) -> tuple[list[str], list[str]]:
    ids = _catalog_ids()
    if not ids:
        # Catalog failed to load — allow primary only (degraded).
        return ([plan[0]] if plan else []), (plan[1:] if len(plan) > 1 else [])
    available = [t for t in plan if t in ids]
    missing = [t for t in plan if t not in ids]
    return available, missing


def _verify_from_result(action: str, result: dict[str, Any]) -> dict[str, Any]:
    """Lightweight verify — evidence from factual packet / status fields."""
    packet = result.get("factual_packet") if isinstance(result.get("factual_packet"), dict) else {}
    ok = bool(result.get("reply")) and not result.get("blocked")
    if action in ("verify_stream", "ensure_playback"):
        status = (
            packet.get("verification_status")
            or packet.get("status")
            or result.get("action_type")
            or ""
        )
        ok = ok and "fail" not in str(status).lower() and "blocked" not in str(status).lower()
    if action == "now_playing":
        title = packet.get("now_playing_title") or packet.get("title")
        ok = ok and bool(title) and str(title).lower() not in ("unknown", "n/a", "")
    if action == "get_station_schedule":
        ok = ok and packet.get("tool") == "get_station_schedule" and packet.get("sqlite_grid_used") is False
        ok = ok and packet.get("status") in ("ok", "cannot")
        if packet.get("status") == "cannot":
            ok = False
    if action == "whats_next":
        ok = packet.get("status") == "ok" and bool((packet.get("playing_next") or {}).get("title"))
    if action == "assign_capsule_to_playlist":
        ok = packet.get("status") in ("ok", "needs_confirmation")
    if action == "arm_deferred_status":
        ok = packet.get("status") == "armed"
    return {
        "ok": bool(ok),
        "action": action,
        "evidence": {
            "action_type": result.get("action_type"),
            "has_packet": bool(packet),
            "packet_tool": packet.get("tool"),
        },
    }


def run_owner_kernel(
    *,
    message: str,
    interpreter_packet: dict[str, Any],
    selected_model: str,
    mem_packet: dict[str, Any],
    mem_context: str,
    tb: Any,
    live_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Execute one owner work run. Returns ops-style result dict or cannot result.
    None = caller should use non-kernel path (should not happen if should_enter_kernel).
    """
    action = (interpreter_packet.get("action") or "unknown").strip().lower()
    slots = dict(interpreter_packet.get("slots") or {})

    # Pre-tool cannot (pause / wake / deferred worker off)
    reason = unavailable_action_reason(message)
    if reason:
        pkt = build_cannot_packet(reason)
        run = new_run(goal=message, action=action or "cannot", slots=slots)
        run["status"] = "cannot"
        run["factual_packet"] = pkt
        run["verification"] = {"ok": False, "reason": reason}
        if tb is not None:
            try:
                tb.final_reply_source = "truth_gate"
                tb.route = "truth_gate_cannot"
            except Exception:
                pass
        return {
            "reply": build_cannot_reply(reason),
            "action_type": "CANNOT",
            "factual_packet": pkt,
            "owner_run": run,
            "gemini_calls": 0,
        }

    # Deferred arm only when interpreter selected arm_deferred_status (no phrase remap).

    if not should_enter_kernel(action, message):
        return None

    plan = _plan_for(action)
    available, missing = _inventory(plan)
    run: OwnerRun = new_run(
        goal=message,
        action=action,
        slots=slots,
        success_criteria=f"{action} completed with verifiable evidence",
    )
    run["plan_steps"] = plan
    run["tools_needed"] = plan
    run["tools_available"] = available
    run["tools_missing"] = missing
    run["status"] = "running"

    if not available and missing:
        pkt = build_cannot_packet("tool_missing", detail=",".join(missing))
        run["status"] = "cannot"
        run["factual_packet"] = pkt
        return {
            "reply": build_cannot_reply("tool_missing") + f" Missing: {', '.join(missing)}.",
            "action_type": "CANNOT",
            "factual_packet": pkt,
            "owner_run": run,
            "gemini_calls": 0,
        }

    # Act via existing operations workflows (no twin executor).
    from services.brain import operations_workflows

    op_result = operations_workflows.try_handle_interpreter_packet(
        message=message,
        interpreter_packet=interpreter_packet,
        selected_model=selected_model,
        mem_packet=mem_packet,
        mem_context=mem_context,
        tb=tb,
    )
    if op_result is None:
        # Try direct live_ops for catalog-only tools like now_playing
        from services.tools.live_ops_executor import try_execute_live_ops

        op_result = try_execute_live_ops(action, slots, snapshot=live_snapshot or {}, owner_message=message)

    if not isinstance(op_result, dict):
        pkt = build_cannot_packet("no_tool_result", detail=f"no_handler:{action}")
        run["status"] = "cannot"
        run["factual_packet"] = pkt
        return {
            "reply": build_cannot_reply("no_tool_result"),
            "action_type": "CANNOT",
            "factual_packet": pkt,
            "owner_run": run,
            "gemini_calls": 0,
        }

    # Optional safe follow-up loop (ADR-005 wrapped as execute phase)
    try:
        from services.tools.loop import extend_live_ops_result

        op_result = extend_live_ops_result(
            message=message,
            first_result=op_result,
            first_action=action,
            tb=tb,
        )
    except Exception as exc:
        logger.debug("[run_kernel] loop skip: %s", exc)

    op_result = dict(op_result)
    packet = op_result.get("factual_packet") if isinstance(op_result.get("factual_packet"), dict) else {}
    job_id = op_result.get("job_id")
    # Background creative may return job_id with a thin packet — normalize.
    if job_id and (not packet or not packet.get("tool")):
        packet = {
            "tool": action or "background_job",
            "status": str(packet.get("status") or "accepted"),
            "job_id": job_id,
        }
        op_result["factual_packet"] = packet

    # Empty/weak act: reply without tool/job facts → Cannot (no soft "kar rahi").
    if (not packet or not packet.get("tool")) and not job_id:
        pkt = build_cannot_packet("no_tool_result", detail=f"empty_act:{action}")
        run["status"] = "cannot"
        run["factual_packet"] = pkt
        run["verification"] = {"ok": False, "reason": "no_tool_result"}
        if tb is not None:
            try:
                tb.final_reply_source = "truth_gate"
                tb.route = "owner_run_kernel_empty_act"
            except Exception:
                pass
        return {
            "reply": build_cannot_reply("no_tool_result"),
            "action_type": "CANNOT",
            "factual_packet": pkt,
            "owner_run": run,
            "gemini_calls": int(op_result.get("gemini_calls") or 0),
        }

    if packet:
        run["observations"].append(packet)
        run["factual_packet"] = packet

    verification = _verify_from_result(action, op_result)
    run["verification"] = verification
    run["status"] = "verified" if verification.get("ok") else "failed"

    op_result["owner_run"] = run
    if not op_result.get("factual_packet") and run.get("factual_packet"):
        op_result["factual_packet"] = run["factual_packet"]

    # Verify fail: Cannot-style honesty — never leave success-sounding soft progress.
    if not verification.get("ok"):
        st = str(packet.get("status") or "").strip().lower()
        if st == "needs_confirmation":
            # Confirm theatre is intentional; keep pending reply + packet.
            pass
        elif st in ("cannot", "error", "failed", "") or packet.get("tool") == "truth_gate":
            pkt = (
                packet
                if packet.get("tool") == "truth_gate"
                else build_cannot_packet("no_tool_result", detail=f"verify_failed:{action}")
            )
            run["status"] = "cannot"
            run["factual_packet"] = pkt
            op_result["reply"] = build_cannot_reply("no_tool_result")
            op_result["factual_packet"] = pkt
            op_result["action_type"] = "CANNOT"
        else:
            base = str(op_result.get("reply") or "").strip()
            op_result["reply"] = (
                build_cannot_reply("no_tool_result")
                + f" Verify failed for {action}."
                + (f" Evidence: {base[:180]}" if base else "")
            )
            op_result["action_type"] = op_result.get("action_type") or "CANNOT"

    if tb is not None:
        try:
            tb.final_reply_source = tb.final_reply_source or "owner_run_kernel"
            tb.route = getattr(tb, "route", None) or "owner_run_kernel"
        except Exception:
            pass

    return op_result


__all__ = ["run_owner_kernel", "should_enter_kernel"]

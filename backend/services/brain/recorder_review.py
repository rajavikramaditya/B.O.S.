"""Owner-only read-only review of command-center interaction recorder.

Deterministic layer returns a FACTUAL DATA PACKET only.
Final owner-facing Hinglish reply is composed by the conversation LLM
(via maybe_humanize_report / humanize_factual_reply) — never a canned phrase.

Never edits/deletes recorder data. Never returns secrets, unlock phrases, or prompts.
"""
from __future__ import annotations

import json
from typing import Any

import database as db


def _clip(text: str | None, n: int = 120) -> str:
    value = (text or "").strip().replace("\n", " ")
    return value if len(value) <= n else value[: n - 3] + "..."


def _parse_trace(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _turn_flags(trace: dict[str, Any], action: str | None) -> list[str]:
    flags: list[str] = []
    if trace.get("pending_cleared_without_execute"):
        flags.append("pending_cleared_without_execute")
    if trace.get("reached_interpreter") is False and trace.get("short_circuit_reason"):
        flags.append(f"short_circuit:{trace.get('short_circuit_reason')}")
    if (action or "") == "SEND_AZURACAST_CONFIRM":
        flags.append("confirm_theatre")
    if (action or "") in ("SEND_AZURACAST_FAILED", "SEND_AZURACAST_BLOCKED"):
        flags.append("azura_fail_or_block")
    if trace.get("memory_hits_count") == 0 and (action or "") == "PERMANENT_MEMORY_RETRIEVAL":
        flags.append("memory_miss")
    if trace.get("customer_history_source") == "none":
        flags.append("customer_history_none")
    return flags


def build_recorder_review(
    *,
    limit: int = 12,
    channel: str | None = None,
) -> dict[str, Any]:
    """Return structured recorder facts for LLM final-reply composition (read-only)."""
    limit = max(3, min(int(limit or 12), 30))
    rows = db.list_command_center_turns(limit=limit)
    turns_out: list[dict[str, Any]] = []
    findings: list[str] = []

    for row in rows:
        ch = str(row.get("channel") or "")
        if channel and ch != channel:
            continue
        trace = _parse_trace(row.get("trace_json"))
        action = row.get("action_type")
        flags = _turn_flags(trace, action)
        for f in flags:
            if f not in findings:
                findings.append(f)
        turns_out.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "channel": ch,
                "action_type": action,
                "route": row.get("route") or trace.get("route"),
                "reached_interpreter": trace.get("reached_interpreter"),
                "short_circuit_reason": trace.get("short_circuit_reason"),
                "capsule_id": trace.get("capsule_id") or trace.get("capsule_id_resolved"),
                "agent_loop_steps": trace.get("agent_loop_steps"),
                "factual_packet_digest": trace.get("factual_packet_digest"),
                "flags": flags,
                "user_input": _clip(row.get("user_input"), 100),
                "assistant_reply": _clip(row.get("assistant_reply"), 140),
            }
        )

    packet = {
        "tool": "check_interaction_recorder",
        "mode": "read_only",
        "turn_count": len(turns_out),
        "findings": findings,
        "recent_turns": turns_out[:5],
        "notes": [
            "Recorder was read only; no edit or delete performed.",
            "Owner-facing reply must be composed by the conversation LLM from this packet.",
        ],
    }
    # Compact factual string for humanize_factual_reply (DATA block) — not owner speech.
    factual_text = json.dumps(packet, ensure_ascii=False, default=str)

    return {
        "success": True,
        "read_only": True,
        "turn_count": len(turns_out),
        "findings": findings,
        "turns": turns_out,
        "factual_packet": packet,
        # `reply` here is FACTS for the LLM humanizer, not the final owner message.
        "reply": factual_text,
    }


__all__ = ["build_recorder_review"]

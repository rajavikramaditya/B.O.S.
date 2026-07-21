"""Bounded + deep multi-tool loop — Cursor-like LLM observe→act→observe (Phase 6).

Seed action comes from the owner interpreter. Further steps are chosen by
neena_agent_step (LLM JSON) from a safe read/recommend allowlist only.
Never auto-chains protected / confirm-gated actions. No shell/SQL.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import services.brain.feature_flags as feature_flags
from services.agent.step import choose_next_agent_step
from services.tools.catalog import followup_ids

# Re-export for tests / callers that imported from this module
def __getattr__(name: str):
    if name == "SAFE_FOLLOWUP_ACTIONS":
        return followup_ids()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

logger = logging.getLogger(__name__)

_MAX_STEPS_BOUNDED = 5  # includes the first tool already executed
_MAX_STEPS_DEEP = 8

_STOP_ACTION_TYPES = frozenset(
    {
        "SEND_AZURACAST",
        "SEND_AZURACAST_CONFIRM",
        "SEND_AZURACAST_BLOCKED",
        "GENERATE_AUDIO",
        "PREPARE_CAPSULE_AUDIO",
        "REJECT_CAPSULE",
        "APPROVE_CAPSULE",
        "PROPOSE_PERMANENT_MEMORY",
        "MANAGE_MEMORY",
    }
)


def _max_steps() -> int:
    from services.llm.quota_gatekeeper import agent_loop_max_steps

    deep = feature_flags.deep_agent_loop_enabled()
    return agent_loop_max_steps(_MAX_STEPS_BOUNDED, _MAX_STEPS_DEEP, deep=deep)


def _clip_packet(pkt: Any, n: int = 500) -> str:
    if not isinstance(pkt, dict):
        return ""
    try:
        raw = json.dumps(pkt, ensure_ascii=False, default=str)
    except Exception:
        raw = str(pkt)
    raw = raw.replace("\n", " ").strip()
    return raw if len(raw) <= n else raw[: n - 3] + "..."


def _factual_digest(packets: list[Any], steps: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    for s in steps:
        action = s.get("action") or "?"
        at = s.get("action_type") or ""
        bits.append(f"{action}:{at}")
    head = "agent_loop steps=" + ",".join(bits[:8])
    for pkt in packets[-3:]:
        if isinstance(pkt, dict):
            status = pkt.get("status") or pkt.get("tool") or ""
            nxt = pkt.get("recommended_next_action") or pkt.get("next_step") or ""
            if status or nxt:
                bits.append(f"{status} next={nxt}".strip())
    body = " | ".join(str(b) for b in bits if b)[:700]
    return f"{head}. {body}".strip()


def _snapshot_summary(snap: dict[str, Any] | None) -> str:
    if not isinstance(snap, dict) or not snap:
        return ""
    try:
        from services.brain.live_state_snapshot import format_snapshot_for_interpreter

        return format_snapshot_for_interpreter(snap)[:900]
    except Exception:
        try:
            return json.dumps(
                {
                    "stream": snap.get("stream"),
                    "recommended_next_action": snap.get("recommended_next_action"),
                },
                ensure_ascii=False,
                default=str,
            )[:500]
        except Exception:
            return ""


def _execute_followup(
    action: str,
    slots: dict[str, Any],
    *,
    snap: dict[str, Any],
    message: str,
) -> dict[str, Any] | None:
    """Run one safe follow-up via the tool catalog."""
    from services.tools.catalog import ToolContext, execute, followup_ids, get

    action = (action or "").strip().lower()
    if action not in followup_ids():
        return None
    spec = get(action)
    if spec is None:
        return None
    return execute(
        action,
        ToolContext(
            action=action,
            slots=dict(slots or {}),
            snapshot=snap,
            owner_message=message or "",
        ),
    )


def _try_synthesize_reply(
    *,
    message: str,
    packets: list[Any],
    steps: list[dict[str, Any]],
    digest: str,
    tb: Any,
) -> str | None:
    try:
        from services.brain.conversation import synthesize_agent_loop_reply

        return synthesize_agent_loop_reply(
            message=message,
            packets=packets,
            steps=steps,
            factual_digest=digest,
            tb=tb,
        )
    except Exception:
        return None


def extend_live_ops_result(
    *,
    message: str,
    first_result: dict[str, Any],
    first_action: str,
    tb: Any,
) -> dict[str, Any]:
    """Maybe chain safe follow-up tools via LLM agent step. Returns enriched result."""
    if not feature_flags.bounded_tool_loop_enabled() and not feature_flags.deep_agent_loop_enabled():
        return first_result
    if not first_result or first_result.get("require_confirmation"):
        return first_result
    at = str(first_result.get("action_type") or "").upper()
    if at in _STOP_ACTION_TYPES or "CONFIRM" in at or "BLOCKED" in at:
        return first_result

    from services.brain.live_state_snapshot import build_neena_live_state_snapshot

    deep = feature_flags.deep_agent_loop_enabled()
    max_steps = _max_steps()

    steps: list[dict[str, Any]] = [
        {
            "n": 1,
            "action": first_action,
            "action_type": first_result.get("action_type"),
            "ok": first_result.get("ok", True),
            "source": "seed",
            "decision": "seed",
            "reply_clip": str(first_result.get("reply") or "")[:220],
            "packet_clip": _clip_packet(first_result.get("factual_packet")),
        }
    ]
    packets: list[Any] = []
    if isinstance(first_result.get("factual_packet"), dict):
        packets.append(first_result["factual_packet"])

    current = first_result
    seen = {(first_action or "").strip().lower()}

    wc_block = ""
    pack_text = ""
    try:
        from services.agent.working_context import format_working_context_block
        from services.agent.system_knowledge_pack import system_knowledge_pack_text

        wc_block = format_working_context_block()
        pack_text = system_knowledge_pack_text()
    except Exception:
        pass

    for n in range(2, max_steps + 1):
        remaining = max_steps - n + 1
        try:
            snap = build_neena_live_state_snapshot()
        except Exception:
            snap = {}

        choice = choose_next_agent_step(
            owner_goal=message,
            steps=steps,
            remaining_budget=remaining,
            working_context_block=wc_block,
            system_pack=pack_text,
            live_snapshot_summary=_snapshot_summary(snap),
        )
        decision = str(choice.get("decision") or "done").lower()
        try:
            tb.blink(
                "agent_step",
                n=n,
                decision=decision,
                action=choice.get("action"),
                reason=choice.get("reason"),
            )
        except Exception:
            pass

        if decision in ("done", "clarify"):
            break
        if decision == "confirm":
            try:
                tb.step("tool_loop", "Agent step requested owner confirm — stopping chain")
            except Exception:
                pass
            break

        nxt = (choice.get("action") or "").strip().lower()
        slots = choice.get("slots") if isinstance(choice.get("slots"), dict) else {}
        if not nxt or nxt not in followup_ids() or nxt in seen:
            break

        try:
            nxt_res = _execute_followup(nxt, slots, snap=snap, message=message)
        except Exception as exc:
            logger.debug("tool loop step failed: %s", type(exc).__name__)
            break
        if not nxt_res:
            break

        seen.add(nxt)
        step_rec = {
            "n": n,
            "action": nxt,
            "action_type": nxt_res.get("action_type"),
            "ok": nxt_res.get("ok", True),
            "source": "agent_step",
            "decision": "continue",
            "reason": choice.get("reason"),
            "reply_clip": str(nxt_res.get("reply") or "")[:220],
            "packet_clip": _clip_packet(nxt_res.get("factual_packet")),
        }
        steps.append(step_rec)
        if isinstance(nxt_res.get("factual_packet"), dict):
            packets.append(nxt_res["factual_packet"])
        try:
            tb.blink(
                "tool_loop_step",
                n=n,
                action=nxt,
                action_type=nxt_res.get("action_type"),
                source="agent_step",
            )
            tb.step("tool_loop", f"{'Deep' if deep else 'Bounded'} agent follow-up #{n}: {nxt}")
        except Exception:
            pass

        current = nxt_res
        if nxt_res.get("require_confirmation"):
            break
        nat = str(nxt_res.get("action_type") or "").upper()
        if nat in _STOP_ACTION_TYPES or "CONFIRM" in nat:
            break

    if len(steps) <= 1:
        return first_result

    digest = _factual_digest(packets, steps)
    merged = dict(current)
    merged["factual_packet"] = {
        "tool": "agent_loop",
        "status": "ok",
        "steps": [
            {
                "n": s.get("n"),
                "action": s.get("action"),
                "action_type": s.get("action_type"),
                "ok": s.get("ok"),
                "source": s.get("source"),
                "decision": s.get("decision"),
                "reason": s.get("reason"),
            }
            for s in steps
        ],
        "step_count": len(steps),
        "packets": packets,
        "first_action": first_action,
        "final_action": steps[-1].get("action"),
        "deep": deep,
        "factual_digest": digest,
    }
    # Prefer last step reply as short factual fallback; synthesis may replace.
    fallback_parts = [
        str(first_result.get("reply") or "").strip(),
        str(current.get("reply") or "").strip() if current is not first_result else "",
    ]
    merged["reply"] = " | ".join(p for p in fallback_parts if p)[:900] or digest

    synthesized = _try_synthesize_reply(
        message=message,
        packets=packets,
        steps=merged["factual_packet"]["steps"],
        digest=digest,
        tb=tb,
    )
    if synthesized:
        merged["reply"] = synthesized[:1500]

    merged["action_type"] = current.get("action_type") or first_result.get("action_type")
    if first_result.get("job_id") and not merged.get("job_id"):
        merged["job_id"] = first_result.get("job_id")
    # Stable top-level keys for Command Center recorder whitelist
    merged["agent_loop_steps"] = list(merged["factual_packet"]["steps"])
    merged["factual_packet_digest"] = digest
    try:
        tb.blink("tool_loop_done", steps=len(steps), deep=deep, tool="agent_loop")
    except Exception:
        pass
    return merged


__all__ = ["extend_live_ops_result", "SAFE_FOLLOWUP_ACTIONS"]

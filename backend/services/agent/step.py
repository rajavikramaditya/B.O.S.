"""Mid-loop agent step chooser — Cursor-like observe→decide (Phase 6).

Never re-runs interpret_owner_command on the raw owner message (avoids
broadcast/creative reclassify hijacks). Chooses only from a safe allowlist
or stop decisions. Fail-closed to done on bad JSON / timeout / cooldown.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

import services.llm.provider_router as pr
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

AGENT_STEP_TIMEOUT_SECONDS = 12.0
GEMMA_SOFT_TIMEOUT_SECONDS = 6.0
_CLIP_PACKET = 600
_CLIP_GOAL = 400

# Read / recommend only — derived from catalog followup_ok (risk=read).
def _followup_ids() -> frozenset:
    from services.tools.catalog import followup_ids

    return followup_ids()


def __getattr__(name: str):
    if name == "SAFE_FOLLOWUP_ACTIONS":
        return _followup_ids()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _agent_step_system() -> str:
    from services.tools.catalog import build_followup_allowlist_text

    allow = build_followup_allowlist_text()
    return f"""You are Neena's mid-turn agent planner (Cursor-style observe→act).
Sir already started a station-ops turn. You see the owner goal and tool observations so far.
Return ONLY valid JSON (no markdown):

{{
  "decision": "continue" | "done" | "confirm" | "clarify",
  "action": "<safe tool name or null>",
  "slots": {{}},
  "reason": "short"
}}

Rules:
- continue: need ONE more SAFE read/recommend tool from this allowlist only:
  {allow}
- done: enough facts to answer Sir (prefer done when goal is satisfied)
- confirm: next needed step is a protected WRITE (AzuraCast, real TTS, approve, delete, restart) — do NOT invent that action; set action null
- clarify: need a short question to Sir; action null
- Never invent tool results. Never pick write/broadcast/TTS/delete/memory-propose actions.
- Do not repeat an action already in STEPS unless Sir's goal clearly requires a fresh check.
- Prefer the smallest number of extra tools.
"""


_DECISIONS = frozenset({"continue", "done", "confirm", "clarify"})


def _clip(text: Any, n: int) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        got = json.loads(raw)
        return got if isinstance(got, dict) else None
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        got = json.loads(m.group(0))
        return got if isinstance(got, dict) else None
    except Exception:
        return None


def _normalize_decision(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Fail-closed normalize. Always returns a safe decision dict."""
    if not isinstance(raw, dict):
        return {"decision": "done", "action": None, "slots": {}, "reason": "invalid_json"}
    decision = str(raw.get("decision") or "done").strip().lower()
    if decision not in _DECISIONS:
        decision = "done"
    action = raw.get("action")
    if action is not None:
        action = str(action).strip().lower() or None
    slots = raw.get("slots") if isinstance(raw.get("slots"), dict) else {}
    reason = _clip(raw.get("reason") or decision, 160)

    if decision == "continue":
        if not action or action not in _followup_ids():
            return {
                "decision": "done",
                "action": None,
                "slots": {},
                "reason": "unsafe_or_missing_action",
            }
        return {"decision": "continue", "action": action, "slots": slots, "reason": reason}

    # confirm / clarify / done — never carry a write action
    return {"decision": decision, "action": None, "slots": {}, "reason": reason}


def _model_chain(api_key: str) -> list[str]:
    chain: list[str] = []
    primary = pr.resolve_model_for_role("COMMAND_INTERPRETER_MODEL")
    if primary and not pr.is_disallowed_normal_flow_model(primary):
        chain.append(primary)
    gemini_fb = pr.resolve_and_verify_model("gemini-3.1-flash-lite", api_key)
    if gemini_fb and gemini_fb not in chain and not pr.is_disallowed_normal_flow_model(gemini_fb):
        chain.append(gemini_fb)
    return chain


def _call_step_model(
    resolved_id: str,
    api_key: str,
    system_prompt: str,
    user_text: str,
    timeout_seconds: float,
    *,
    wait_out_cooldown: bool = False,
) -> tuple[dict[str, Any] | None, str, str]:
    provider = "gemma" if "gemma" in resolved_id else "gemini"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 256,
            "responseMimeType": "application/json",
        },
    }
    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=timeout_seconds,
            priority="owner",
            purpose="agent_step",
            wait_out_cooldown=wait_out_cooldown,
        )
        use_id = meta.get("model_id") or resolved_id
        provider = "gemma" if "gemma" in use_id else "gemini"
        if status != "available" or not data:
            mapped = status if status in ("cooldown", "timeout", "rate_limited", "quota_deferred") else "error"
            return None, provider, mapped
        parts = (
            ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        )
        text = ""
        for p in parts:
            if isinstance(p, dict) and p.get("text"):
                text += p["text"]
        return _extract_json(text), provider, "available"
    except Exception as exc:
        logger.debug("agent_step model fail: %s", type(exc).__name__)
        return None, provider, "error"


def _format_steps(steps: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        n = s.get("n") or "?"
        action = s.get("action") or "?"
        at = s.get("action_type") or ""
        ok = s.get("ok", True)
        pkt = s.get("packet_clip") or s.get("reply_clip") or ""
        lines.append(f"{n}. action={action} type={at} ok={ok} facts={_clip(pkt, 220)}")
    return "\n".join(lines) if lines else "(none)"


def choose_next_agent_step(
    *,
    owner_goal: str,
    steps: list[dict[str, Any]],
    remaining_budget: int,
    working_context_block: str = "",
    system_pack: str = "",
    live_snapshot_summary: str = "",
) -> dict[str, Any]:
    """Pick continue/done/confirm/clarify. Never calls interpret_owner_command."""
    if remaining_budget <= 0:
        return {"decision": "done", "action": None, "slots": {}, "reason": "budget_exhausted"}

    api_key = pr.get_gemini_api_key()
    if not api_key:
        return {"decision": "done", "action": None, "slots": {}, "reason": "no_api_key"}

    chain = _model_chain(api_key)
    if not chain:
        return {"decision": "done", "action": None, "slots": {}, "reason": "model_unavailable"}

    system_prompt = _agent_step_system()
    if system_pack:
        system_prompt += f"\n\nSYSTEM PACK (constraints):\n{_clip(system_pack, 1200)}"
    if working_context_block:
        system_prompt += f"\n\n{working_context_block[:800]}"

    user_text = (
        f"OWNER_GOAL: {_clip(owner_goal, _CLIP_GOAL)}\n"
        f"REMAINING_TOOL_BUDGET: {remaining_budget}\n"
        f"LIVE_SNAPSHOT:\n{_clip(live_snapshot_summary, 800) or '(none)'}\n"
        f"STEPS_SO_FAR:\n{_format_steps(steps)}\n"
        "Decide the next JSON decision now."
    )

    for idx, resolved_id in enumerate(chain):
        soft = "gemma" in resolved_id and idx == 0 and len(chain) > 1
        if soft and pr.is_model_penalized(resolved_id):
            continue
        timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else AGENT_STEP_TIMEOUT_SECONDS
        is_last = idx == len(chain) - 1
        packet, _provider, status = _call_step_model(
            resolved_id,
            api_key,
            system_prompt,
            user_text,
            timeout,
            wait_out_cooldown=is_last,
        )
        if status == "available" and packet is not None:
            return _normalize_decision(packet)
        if status in ("cooldown", "timeout") and not is_last:
            continue
        if status in ("cooldown", "timeout") and is_last:
            return {"decision": "done", "action": None, "slots": {}, "reason": status}

    return {"decision": "done", "action": None, "slots": {}, "reason": "chooser_failed"}


__all__ = [
    "SAFE_FOLLOWUP_ACTIONS",
    "choose_next_agent_step",
    "_normalize_decision",
]

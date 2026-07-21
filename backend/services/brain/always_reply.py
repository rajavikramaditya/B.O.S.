"""Crash / empty-payload safety net only — NOT a normal conversational path.

Owner rule: Gemma + flash-lite are both available. A canned reply should almost
never appear. Normal path = try primary, then secondary model. Canned text is
only for: process crash, empty dict, or BOTH models truly unavailable (quota /
no key). Slow internet → wait on the model; local loop → fix the loop — do not
paper over with a fake "main yahin hoon" line.
"""
from __future__ import annotations

from typing import Any


# Honest rare-case copy — dual quota / no key / hard crash only.
DUAL_MODEL_EXHAUSTED = (
    "Sir, is waqt dono models (Gemma aur flash-lite) jawab nahi de paaye — "
    "quota/limit ya provider side issue lagta hai. Thodi der baad try kariye; "
    "status buttons se local check chal sakta hai."
)


def ensure_nonempty_reply(reply: str | None, *, reason: str = "empty") -> str:
    text = (reply or "").strip()
    if text:
        return text
    return DUAL_MODEL_EXHAUSTED


def safe_owner_result(
    message: str,
    *,
    reply: str | None = None,
    action_type: str = "DUAL_MODEL_EXHAUSTED",
    error: Exception | None = None,
) -> dict[str, Any]:
    """Minimal result when process_owner_message crashes or returns empty."""
    reply_text = ensure_nonempty_reply(reply)
    # ADR-008: still commit chat STM so continuity hole na bane after crash net.
    try:
        from services.memory.continuity import commit_owner_turn

        commit_owner_turn(
            message or "",
            reply_text,
            action_type=action_type,
            route="dual_model_exhausted_or_crash",
            update_working=True,
        )
    except Exception:
        try:
            from services.memory import adapter as memory_adapter

            if message:
                memory_adapter.save_chat_turn("user", message)
            memory_adapter.save_chat_turn("model", reply_text)
        except Exception:
            pass
    out: dict[str, Any] = {
        "reply": reply_text,
        "action_type": action_type,
        "command_triggered": None,
        "require_confirmation": False,
        "source": "safety_net",
        "route": "dual_model_exhausted_or_crash",
        "final_reply_source": "safety_net",
        "policy_decision": "safety_net",
        "fallback_used": True,
    }
    if error is not None:
        out["model_unavailable_reason"] = type(error).__name__
    return out


__all__ = [
    "DUAL_MODEL_EXHAUSTED",
    "ensure_nonempty_reply",
    "safe_owner_result",
]

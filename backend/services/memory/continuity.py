"""Owner ContinuityLoader — thin MOS aggregator (ADR-008).

One place to load/commit owner short-term continuity. Not a new store.
Does not wrap the customer chat path. Recorder stays caller-owned (audit only).
"""
from __future__ import annotations

from typing import Any

import services.brain.feature_flags as feature_flags


def load_owner_continuity(
    query: str = "",
    *,
    chat_limit: int = 14,
    permanent_limit: int = 8,
) -> dict[str, Any]:
    """Compose owner continuity bundle from existing stores (flags honored)."""
    chat_turns: list[dict] = []
    if feature_flags.conversation_memory_enabled():
        try:
            from services.memory import adapter as memory_adapter

            chat_turns = memory_adapter.load_chat_history_contents(limit=chat_limit) or []
        except Exception:
            chat_turns = []

    working_context: dict[str, Any] = {}
    working_block = ""
    try:
        from services.agent.working_context import (
            format_working_context_block,
            load_working_context,
        )

        working_context = load_working_context() or {}
        working_block = format_working_context_block(working_context) or ""
    except Exception:
        pass

    pending = None
    short_context = ""
    try:
        import services.brain.manager_state as manager_state

        pending = manager_state.get_pending_action()
        short_context = manager_state.build_short_context() or ""
    except Exception:
        pass

    permanent: dict[str, Any] = {}
    skip_recall = False
    try:
        from services.brain.brain import _should_skip_embedding_recall
        if query and _should_skip_embedding_recall(query.lower().strip()):
            skip_recall = True
    except Exception:
        pass

    if skip_recall:
        permanent = {"hits": [], "context_text": ""}
    elif feature_flags.one_brain_foundation_enabled():
        try:
            from services.memory.facade import recall

            permanent = recall(
                role="owner",
                subject_key="owner",
                query=query or "",
                limit=permanent_limit,
            ) or {}
        except Exception:
            permanent = {}
    else:
        try:
            import services.memory.service as memory_service

            permanent = {
                "legacy_packet": memory_service.get_memory_context_packet(query or ""),
                "context_text": "",
                "hits": [],
            }
            pkt = permanent["legacy_packet"] or {}
            permanent["context_text"] = pkt.get("context_text") or ""
            permanent["hits"] = list(pkt.get("hits") or [])
        except Exception:
            permanent = {"hits": [], "context_text": ""}

    return {
        "role": "owner",
        "subject_key": "owner",
        "chat_turns": chat_turns,
        "working_context": working_context,
        "working_block": working_block,
        "pending": pending,
        "short_context": short_context,
        "permanent": permanent,
        "permanent_context_text": (permanent.get("context_text") or ""),
        "permanent_hits": list(permanent.get("hits") or []),
    }


def format_live_clock_block(now=None) -> str:
    """One authoritative IST clock line for owner LLM prompts (recorder gap W1)."""
    from datetime import datetime, timedelta, timezone

    if now is None:
        now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S %A")
    return (
        f"LIVE CLOCK (authority for this turn): IST={stamp}. "
        "Do not reuse older clock times from chat history."
    )


def build_owner_prompt_context(
    query: str = "",
    *,
    chat_limit: int = 14,
    permanent_limit: int = 8,
) -> dict[str, Any]:
    """Single injection helper for owner LLM paths (ADR-008 continuity).

    Returns chat_turns, working_block, short_context, permanent_context_text, clock_block.
    Callers should prefer this over ad-hoc format_working_context_block().
    """
    bundle = load_owner_continuity(
        query,
        chat_limit=chat_limit,
        permanent_limit=permanent_limit,
    )
    return {
        "chat_turns": bundle.get("chat_turns") or [],
        "working_context": bundle.get("working_context") or {},
        "working_block": bundle.get("working_block") or "",
        "short_context": bundle.get("short_context") or "",
        "pending": bundle.get("pending"),
        "permanent_context_text": bundle.get("permanent_context_text") or "",
        "permanent_hits": bundle.get("permanent_hits") or [],
        "clock_block": format_live_clock_block(),
        "session_backend": None,
    }


def commit_owner_turn(
    message: str,
    reply: str,
    *,
    action_type: str | None = None,
    route: str | None = None,
    tb: Any = None,
    require_confirmation: bool = False,
    job_id: str | None = None,
    factual_packet: dict | None = None,
    update_working: bool = True,
) -> None:
    """Persist owner chat STM (+ optional working context). Idempotent-ish: always appends turns."""
    try:
        from services.memory import adapter as memory_adapter

        if message is not None:
            memory_adapter.save_chat_turn("user", message)
        if reply is not None:
            memory_adapter.save_chat_turn("model", reply)
    except Exception:
        pass

    if not update_working:
        return
    try:
        from services.agent.working_context import update_working_context_after_turn

        update_working_context_after_turn(
            message=message or "",
            reply=reply or "",
            action_type=action_type,
            route=route,
            tb=tb,
            require_confirmation=bool(require_confirmation),
            job_id=job_id,
            factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
        )
    except Exception:
        pass


__all__ = [
    "build_owner_prompt_context",
    "commit_owner_turn",
    "format_live_clock_block",
    "load_owner_continuity",
]

"""Plug-and-play memory notebook tools (ADR-013 Part B / AGENTS hygiene).

Interpreter classifies → catalog handler → memory helpers.
No Hindi/Hinglish regex NLU in brain local_router.
"""
from __future__ import annotations

from typing import Any

from services.brain.factual_reply import build_live_ops_result
from services.tools.catalog import ToolContext, ToolSpec, register


def _handle_day_memory_recall(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.day_memory import build_day_recall_packet

    out = build_day_recall_packet(ctx.owner_message or "", lazy_diary=True)
    return build_live_ops_result(
        out.get("action_type") or "DAY_MEMORY_RECALL",
        packet=out.get("factual_packet") or {"tool": "day_memory_recall", "status": "ok"},
        fallback_line=out.get("fallback_line") or "Day memory recall prepared.",
    )


def _handle_future_intention_save(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.future_intention import save_future_intention

    out = save_future_intention(ctx.owner_message or "")
    return build_live_ops_result(
        out.get("action_type") or "FUTURE_INTENTION_SAVED",
        packet=out.get("factual_packet") or {"tool": "future_intention_save", "status": "ok"},
        fallback_line=out.get("fallback_line") or "Future intention save attempted.",
    )


def _handle_future_intention_recall(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.future_intention import build_future_recall_packet

    out = build_future_recall_packet(ctx.owner_message or "")
    return build_live_ops_result(
        out.get("action_type") or "FUTURE_INTENTION_RECALL",
        packet=out.get("factual_packet") or {"tool": "future_intention_recall", "status": "ok"},
        fallback_line=out.get("fallback_line") or "Future intention recall prepared.",
    )


def _handle_future_intention_lifecycle(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.future_intention import apply_lifecycle

    out = apply_lifecycle(ctx.owner_message or "")
    return build_live_ops_result(
        out.get("action_type") or "FUTURE_INTENTION_COMPLETE",
        packet=out.get("factual_packet") or {"tool": "future_intention_lifecycle", "status": "ok"},
        fallback_line=out.get("fallback_line") or "Future intention lifecycle attempted.",
    )


def _handle_self_profile(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.self_narrative import format_self_profile_answer

    del ctx
    who = format_self_profile_answer() or {}
    return build_live_ops_result(
        "SELF_PROFILE",
        packet=who.get("factual_packet") or {"tool": "self_profile", "status": "ok"},
        fallback_line=who.get("fallback_line") or "Self profile notebook empty.",
    )


def _handle_self_life_story(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.self_narrative import format_life_story_answer

    del ctx
    life = format_life_story_answer() or {}
    return build_live_ops_result(
        "SELF_LIFE_STORY",
        packet=life.get("factual_packet") or {"tool": "self_life_story", "status": "ok"},
        fallback_line=life.get("fallback_line") or "Life episodes notebook empty.",
    )


def _handle_self_architecture(ctx: ToolContext) -> dict[str, Any] | None:
    from services.memory.self_narrative import format_architecture_answer

    del ctx
    arch = format_architecture_answer() or {}
    return build_live_ops_result(
        "SELF_ARCHITECTURE",
        packet=arch.get("factual_packet") or {"tool": "self_architecture", "status": "ok"},
        fallback_line=arch.get("fallback_line") or "Architecture notebook empty.",
    )


def register_memory_notebook_tools() -> None:
    specs = (
        ToolSpec(
            id="day_memory_recall",
            description="Recall owner day/week diary + recent CC turns for a asked day window",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Day / calendar memory recall",
            handler=_handle_day_memory_recall,
        ),
        ToolSpec(
            id="future_intention_save",
            description="Save an owner future plan/intention into permanent memory",
            risk="safe_write",
            route="live_ops",
            category="memory",
            capability_label="Save future intention",
            handler=_handle_future_intention_save,
        ),
        ToolSpec(
            id="future_intention_recall",
            description="Recall open future intentions / plans",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Recall future intentions",
            handler=_handle_future_intention_recall,
        ),
        ToolSpec(
            id="future_intention_lifecycle",
            description="Mark future intention complete/cancel/postpone (compound markers)",
            risk="safe_write",
            route="live_ops",
            category="memory",
            capability_label="Future intention lifecycle",
            handler=_handle_future_intention_lifecycle,
        ),
        ToolSpec(
            id="self_profile",
            description="Answer who Neena is from permanent self notebook",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Self profile notebook",
            handler=_handle_self_profile,
        ),
        ToolSpec(
            id="self_life_story",
            description="Answer from curated life episodes notebook",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Life episodes notebook",
            handler=_handle_self_life_story,
        ),
        ToolSpec(
            id="self_architecture",
            description="Answer how Neena's mind/architecture works from notebook",
            risk="read",
            route="live_ops",
            followup_ok=True,
            category="memory",
            capability_label="Mind architecture notebook",
            handler=_handle_self_architecture,
        ),
    )
    for spec in specs:
        register(spec)


__all__ = ["register_memory_notebook_tools"]

"""Live-ops hands — propose permanent memory (ADR-013 Wave 2)."""
from __future__ import annotations

from services.tools.catalog import ToolContext, set_handler


def bind() -> None:
    set_handler("propose_permanent_memory", _make("propose_permanent_memory"))


def _make(action_id: str):
    def _handle(ctx: ToolContext):
        from services.tools.live_ops._dispatch import run_action

        return run_action(action_id, ctx)

    return _handle

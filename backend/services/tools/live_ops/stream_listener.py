"""Live-ops hands — stream verify + listener path (ADR-013 Wave 2)."""
from __future__ import annotations

from services.tools.catalog import ToolContext, set_handler


def bind() -> None:
    set_handler("verify_stream", _make("verify_stream"))
    set_handler("diagnose_listener_path", _make("diagnose_listener_path"))
    set_handler("fix_app_listener_path", _make("fix_app_listener_path"))


def _make(action_id: str):
    def _handle(ctx: ToolContext):
        from services.tools.live_ops._dispatch import run_action

        return run_action(action_id, ctx)

    return _handle

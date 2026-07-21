"""Live-ops hands — AzuraCast pulse / schedule (ADR-013 Wave 2)."""
from __future__ import annotations

from services.tools.catalog import ToolContext, set_handler


def bind() -> None:
    set_handler("now_playing", _make("now_playing"))
    set_handler("get_station_schedule", _make("get_station_schedule"))
    set_handler("whats_next", _make("whats_next"))
    set_handler("assign_capsule_to_playlist", _make("assign_capsule_to_playlist"))


def _make(action_id: str):
    def _handle(ctx: ToolContext):
        from services.tools.live_ops._dispatch import run_action

        return run_action(action_id, ctx)

    return _handle

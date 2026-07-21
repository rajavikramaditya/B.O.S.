"""Live-ops hands — capsule / script / audio / push (ADR-013 Wave 2)."""
from __future__ import annotations

from services.tools.catalog import ToolContext, set_handler


def bind() -> None:
    set_handler("open_latest_script", _make("open_latest_script"))
    set_handler("list_pending_capsules", _make("list_pending_capsules"))
    set_handler("open_latest_capsule", _make("open_latest_capsule"))
    set_handler("capsule_status", _make("capsule_status"))
    set_handler("capsule_status_clarify", _make("capsule_status_clarify"))
    set_handler("approve_latest_script", _make("approve_latest_script"))
    set_handler("generate_audio", _make("generate_audio"))
    set_handler("send_azuracast", _make("send_azuracast"))
    set_handler("ensure_playback", _make("ensure_playback"))
    set_handler("approve_capsule", _make("approve_capsule"))
    set_handler("reject_capsule", _make("reject_capsule"))
    set_handler("prepare_capsule_audio", _make("prepare_capsule_audio"))
    set_handler("needs_revision", _make("needs_revision"))


def _make(action_id: str):
    def _handle(ctx: ToolContext):
        from services.tools.live_ops._dispatch import run_action

        return run_action(action_id, ctx)

    return _handle

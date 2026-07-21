"""Live-ops hands — status / recommend / auth (ADR-013 Wave 2)."""
from __future__ import annotations

from services.tools.catalog import ToolContext, set_handler


def bind() -> None:
    set_handler("capabilities", _make("capabilities"))
    set_handler("model_status", _make("model_status"))
    set_handler("memory_status", _make("memory_status"))
    set_handler("timeout_diagnosis", _make("timeout_diagnosis"))
    set_handler("what_should_i_do_now", _make("what_should_i_do_now"))
    set_handler("pipeline_status", _make("pipeline_status"))
    set_handler("explain_button", _make("explain_button"))
    set_handler("admin_lock", _make("admin_lock"))
    set_handler("auth_session_explain", _make("auth_session_explain"))
    set_handler("vm_status", _make("vm_status"))


def _make(action_id: str):
    def _handle(ctx: ToolContext):
        from services.tools.live_ops._dispatch import run_action

        return run_action(action_id, ctx)

    return _handle

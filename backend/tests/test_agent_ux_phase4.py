"""Phase 4 — feature-flag overrides + working-context public shape."""
from __future__ import annotations

import services.brain.feature_flags as ff


def test_flag_override_beats_env(monkeypatch):
    monkeypatch.delenv("NEENA_BOUNDED_TOOL_LOOP", raising=False)
    ff._OVERRIDES.clear()
    ff._OVERRIDES_LOADED = True
    assert ff.bounded_tool_loop_enabled() is True
    out = ff.set_flag_override("NEENA_BOUNDED_TOOL_LOOP", False)
    assert out.get("ok") is True
    assert ff.bounded_tool_loop_enabled() is False
    ff.set_flag_override("NEENA_BOUNDED_TOOL_LOOP", None)
    assert ff.bounded_tool_loop_enabled() is True


def test_non_toggleable_flag_rejected():
    ff._OVERRIDES.clear()
    ff._OVERRIDES_LOADED = True
    out = ff.set_flag_override("NEENA_SMART_REPLY", False)
    assert out.get("ok") is False
    assert out.get("error") == "flag_not_toggleable"


def test_snapshot_includes_three_agent_flags():
    snap = ff.snapshot_agent_flags()
    assert snap.get("ok") is True
    for key in ff.CC_TOGGLEABLE_FLAGS:
        assert key in snap["flags"]
        assert "enabled" in snap["flags"][key]


def test_public_working_context_shape():
    from routers.neena_agent_ux import _public_working_context

    pub = _public_working_context(
        {
            "open_goal": "verify stream",
            "last_action_type": "PIPELINE_STATUS",
            "pending": {"action_type": "memory_edit", "memory_id": 3},
            "recent_actions": [{"action_type": "MANAGE_MEMORY", "route": "list"}],
            "secret_prompt": "should not leak",
        }
    )
    assert pub["open_goal"] == "verify stream"
    assert pub["pending"]["memory_id"] == 3
    assert "secret_prompt" not in pub

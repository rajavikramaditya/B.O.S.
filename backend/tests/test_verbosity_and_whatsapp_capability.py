"""M-fix — Persistent concise preference + WhatsApp-to-owner push capability.

These guard the two owner-visible fixes:
  1. "keep it short" preference is remembered (and applied to status/diagnostics).
  2. Neena can send status to the owner on WhatsApp (real capability + manifest).

No regex-based NL parsing is asserted here — detection is the interpreter model's job.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.brain.manager_state as manager_state
import services.cockpit.status_fast as csf
from services.brain.command_interpreter import VALID_ACTIONS
from services.brain.capability_manifest import build_capability_manifest


def _reset_state():
    manager_state._state["owner_corrections"] = []
    manager_state._state["concise_mode"] = False
    manager_state._corrections_hydrated = True  # skip Redis hydrate in unit test
    manager_state._concise_hydrated = True


def test_concise_preference_sets_flag_and_remembers_rule():
    _reset_state()
    manager_state.set_response_style(True)
    assert manager_state.is_concise_mode() is True
    # The style rule must be surfaced to the LLM via short context.
    ctx = manager_state.build_short_context()
    assert "short" in ctx.lower()


def test_normal_preference_clears_concise():
    _reset_state()
    manager_state.set_response_style(True)
    manager_state.set_response_style(False)
    assert manager_state.is_concise_mode() is False


def test_station_status_is_short_when_concise():
    _reset_state()
    snapshot = {
        "launch": {"brain_status": "ready"},
        "stream_online": True,
        "local_stats": {"cpu": 10, "ram": 40},
        "memory_stack_summary": {"postgres": "healthy", "redis": "healthy"},
        "broadcast_readiness": {"tts_status": "ready", "can_produce_real_audio": True},
        "whatsapp_gateway": "online",
    }
    manager_state.set_response_style(False)
    full = csf.format_station_status_message(snapshot)
    manager_state.set_response_style(True)
    short = csf.format_station_status_message(snapshot)
    assert short.count("\n") < full.count("\n")
    assert len(short) < len(full)


def test_diagnostics_is_short_when_concise():
    _reset_state()
    snapshot = {
        "stream_online": True,
        "local_stats": {"cpu": 12, "ram": 30},
        "memory_stack_summary": {"postgres": "healthy", "redis": "healthy"},
        "whatsapp_gateway": "online",
    }
    manager_state.set_response_style(False)
    full = csf.format_diagnostics_fast_message(snapshot)
    manager_state.set_response_style(True)
    short = csf.format_diagnostics_fast_message(snapshot)
    assert len(short) < len(full)


def test_new_actions_registered_in_interpreter():
    assert "set_response_style" in VALID_ACTIONS
    assert "send_owner_whatsapp_status" in VALID_ACTIONS


def test_whatsapp_owner_push_capability_present():
    manifest = build_capability_manifest()
    ids = {c["capability_id"] for c in manifest["capabilities"]}
    assert "whatsapp_owner_push" in ids


def test_whatsapp_owner_push_reflects_config(monkeypatch):
    monkeypatch.setenv("OWNER_WHATSAPP_NUMBER", "919999999999")
    cap = next(c for c in build_capability_manifest()["capabilities"] if c["capability_id"] == "whatsapp_owner_push")
    assert cap["available_now"] is True
    monkeypatch.setenv("OWNER_WHATSAPP_NUMBER", "")
    cap2 = next(c for c in build_capability_manifest()["capabilities"] if c["capability_id"] == "whatsapp_owner_push")
    assert cap2["available_now"] is False

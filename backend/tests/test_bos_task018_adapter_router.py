"""Tests for TASK-018: Adapter Router & Capability Integration."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from adapters import AdapterRouter, AdapterResponse


def test_adapter_router_whatsapp():
    res = AdapterRouter.route_action(
        action="send_message",
        channel="whatsapp",
        recipient="919876543210",
        payload={"text": "Hello via router"},
    )
    assert isinstance(res, AdapterResponse)
    assert res.success is True
    assert res.data["channel"] == "whatsapp"


def test_adapter_router_calendar():
    res = AdapterRouter.route_action(
        action="schedule_meeting",
        channel="calendar",
        payload={"title": "Client Review", "time": "2026-07-21 15:00"},
    )
    assert res.success is True
    assert res.data["channel"] == "calendar"
    assert res.data["event_title"] == "Client Review"


def test_adapter_router_fallback():
    res = AdapterRouter.route_action(
        action="unknown_action",
        channel="unsupported_channel",
        payload={"text": "fallback text"},
    )
    assert res.success is True  # Falls back to default messaging adapter (whatsapp)
    assert res.data["channel"] == "whatsapp"

"""Tests for TASK-005: Runtime Event Bus."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.events import (
    EventType,
    RuntimeEvent,
    RuntimeEventBus,
)


def setup_function():
    RuntimeEventBus.clear()


def test_runtime_event_model():
    evt = RuntimeEvent(
        event_type=EventType.INCOMING_MESSAGE,
        payload={"message": "hello"},
        source="whatsapp",
        actor_role="customer",
    )
    assert evt.event_id.startswith("evt_")
    d = evt.to_dict()
    assert d["event_type"] == "INCOMING_MESSAGE"
    assert d["source"] == "whatsapp"


def test_event_bus_subscribe_and_publish():
    received = []

    def handle_msg(event: RuntimeEvent):
        received.append(event.payload.get("message"))
        return "ok"

    sub_id = RuntimeEventBus.subscribe(EventType.INCOMING_MESSAGE, handle_msg)
    assert sub_id.startswith("sub_")

    evt = RuntimeEvent(
        event_type=EventType.INCOMING_MESSAGE,
        payload={"message": "test event message"},
    )
    results = RuntimeEventBus.publish(evt)

    assert len(received) == 1
    assert received[0] == "test event message"
    assert results == ["ok"]

    # Test unsubscribe
    ok = RuntimeEventBus.unsubscribe(sub_id)
    assert ok is True

    RuntimeEventBus.publish(evt)
    assert len(received) == 1  # Unsubscribed, so not called again

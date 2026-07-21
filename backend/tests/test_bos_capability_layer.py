"""Tests for B.O.S. Capability Layer."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from capabilities.base import CapabilityRegistry, BaseCapability, CapabilityResult
from capabilities.messaging import MessagingCapability
from capabilities.scheduling import SchedulingCapability
from capabilities.memory import MemoryCapability
from capabilities.automation import AutomationCapability


def test_capability_registry():
    caps = CapabilityRegistry.list_capabilities()
    assert len(caps) >= 4
    names = [c["name"] for c in caps]
    assert "messaging" in names
    assert "scheduling" in names
    assert "memory" in names
    assert "automation" in names


def test_messaging_capability_lookup():
    cap = CapabilityRegistry.resolve_capability_for_action("notify_owner")
    assert cap is not None
    assert cap.name == "messaging"


def test_scheduling_capability_lookup():
    cap = CapabilityRegistry.resolve_capability_for_action("get_station_schedule")
    assert cap is not None
    assert cap.name == "scheduling"


def test_memory_capability_lookup():
    cap = CapabilityRegistry.resolve_capability_for_action("self_change_status")
    assert cap is not None
    assert cap.name == "memory"


def test_automation_capability_lookup():
    cap = CapabilityRegistry.resolve_capability_for_action("now_playing")
    assert cap is not None
    assert cap.name == "automation"

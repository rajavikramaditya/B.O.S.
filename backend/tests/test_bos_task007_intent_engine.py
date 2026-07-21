"""Tests for TASK-007: Intent Engine."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.intent import IntentEngine, IntentObject, IntentCategory, PriorityLevel, UrgencyLevel
from runtime.observation import ObservationEngine


def test_intent_engine_analysis():
    req = ObservationEngine.observe(
        role="owner",
        message="send_azuracast urgent",
        sender_name="OwnerAdmin",
    )
    intent = IntentEngine.analyze(req)
    assert isinstance(intent, IntentObject)
    assert intent.goal == "send_azuracast urgent"
    assert intent.actor_role == "owner"
    assert intent.priority == PriorityLevel.HIGH
    assert intent.urgency == UrgencyLevel.IMMEDIATE
    assert "messaging" in intent.required_capabilities or "automation" in intent.required_capabilities


def test_intent_engine_customer_chat():
    req = ObservationEngine.observe(
        role="customer",
        message="Radio schedule batao",
        sender_name="Rahul",
        phone="9876543210",
    )
    intent = IntentEngine.analyze(req)
    assert intent.actor_role == "customer"
    assert intent.category == IntentCategory.INQUIRY
    assert intent.actor_id == "Rahul"

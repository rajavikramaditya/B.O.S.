"""Tests for TASK-008: Decision Engine."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.intent import IntentObject, PriorityLevel
from runtime.decision import DecisionEngine, DecisionResult, DecisionRules


def test_decision_engine_evaluation_safe_action():
    intent = IntentObject(
        goal="check status",
        action="now_playing",
        actor_role="owner",
        priority=PriorityLevel.LOW,
    )
    decision = DecisionEngine.evaluate(intent)
    assert isinstance(decision, DecisionResult)
    assert decision.risk_level == "LOW"
    assert decision.business_approval_required is False
    assert decision.can_auto_execute is True
    assert decision.recommended_action == "execute"


def test_decision_engine_protected_action():
    intent = IntentObject(
        goal="send azuracast playlist",
        action="send_azuracast",
        actor_role="owner",
        priority=PriorityLevel.HIGH,
    )
    decision = DecisionEngine.evaluate(intent)
    assert decision.risk_level == "HIGH"
    assert decision.business_approval_required is True
    assert decision.can_auto_execute is False
    assert decision.recommended_action == "confirm"

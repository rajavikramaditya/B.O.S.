"""Tests for TASK-020: Reasoning Engine."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.intent import IntentObject, PriorityLevel
from runtime.reasoning import ReasoningEngine, ReasoningResult


def test_reasoning_engine_analysis():
    intent = IntentObject(
        goal="Open a new branch store",
        action="create_branch",
        actor_role="owner",
        priority=PriorityLevel.HIGH,
        required_capabilities=["documents", "workflow"],
    )
    result = ReasoningEngine.analyze_reasoning(intent)
    assert isinstance(result, ReasoningResult)
    assert len(result.insights) >= 2
    assert "documents" in result.recommended_capabilities
    assert len(result.multi_step_strategy) > 0

"""Tests for TASK-019: AI Orchestrator."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.intent import IntentObject, PriorityLevel
from runtime.orchestrator import AIOrchestrator, OrchestratorState


def test_ai_orchestrator_routing():
    intent = IntentObject(
        goal="check owner status and history",
        action="status_check",
        actor_role="owner",
        priority=PriorityLevel.HIGH,
    )
    state = AIOrchestrator.orchestrate(intent)
    assert isinstance(state, OrchestratorState)
    assert "reasoning_engine" in state.participating_engines
    assert "decision_engine" in state.participating_engines
    assert "business_graph" in state.participating_engines
    assert "workflow_memory" in state.participating_engines
    assert "ROUTING_DETERMINED" in state.completed_steps

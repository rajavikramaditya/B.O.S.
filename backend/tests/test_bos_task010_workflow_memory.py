"""Tests for TASK-010: Workflow Memory."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.workflow_memory import (
    WorkflowMemory,
    WorkflowStore,
    PatternStore,
    HistoryStore,
    WorkflowIndex,
)


def setup_function():
    WorkflowMemory.clear_all()


def test_workflow_memory_record_run_and_pattern_recall():
    rec = {
        "execution_id": "exec_test_1",
        "goal": "send_azuracast_playlist",
        "status": "COMPLETED",
        "visited_nodes": ["START", "OBSERVE", "POLICY", "EXECUTE", "END"],
    }
    WorkflowMemory.record_run("exec_test_1", rec)

    retrieved = WorkflowStore.get_execution("exec_test_1")
    assert retrieved is not None
    assert retrieved["status"] == "COMPLETED"

    pattern = WorkflowMemory.recall_pattern_for_goal("send_azuracast_playlist")
    assert pattern is not None
    assert pattern["goal"] == "send_azuracast_playlist"
    assert pattern["visited_nodes"] == ["START", "OBSERVE", "POLICY", "EXECUTE", "END"]


def test_workflow_memory_history_logging():
    WorkflowMemory.log_decision({"action": "generate_audio", "risk": "MEDIUM"})
    WorkflowMemory.log_approval({"action": "send_azuracast", "status": "APPROVED"})
    WorkflowMemory.log_recovery({"node": "RETRY", "status": "RECOVERED"})

    hist = WorkflowMemory.get_history()
    assert len(hist["decisions"]) == 1
    assert len(hist["approvals"]) == 1
    assert len(hist["recoveries"]) == 1

"""Tests for TASK-006: Execution Context."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.context import ExecutionContext
from runtime.state import RuntimeState


def test_execution_context_model():
    ctx = ExecutionContext(
        business_id="corp_123",
        actor="Ravi",
        role="owner",
        permissions=["read_status", "execute_command"],
    )
    assert ctx.execution_id.startswith("exec_")
    assert ctx.business_id == "corp_123"
    assert ctx.role == "owner"
    assert ctx.has_permission("read_status") is True
    assert ctx.has_permission("delete_db") is False


def test_execution_context_with_runtime_state():
    state = RuntimeState()
    ctx = ExecutionContext(
        actor="OwnerAdmin",
        role="owner",
        permissions=["*"],
        runtime_state=state,
    )
    assert ctx.has_permission("anything") is True
    assert ctx.runtime_state is state
    d = ctx.to_dict()
    assert d["role"] == "owner"
    assert d["runtime_state"]["current_node"] == "START"

"""Tests for TASK-042 to TASK-049: Execution Pipeline & Command Bus."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core.execution import (
    CommandBus,
    CommandResult,
    ExecutionState,
    ExecutionTransaction,
)
from core.execution.reference import EchoCommand


def setup_function():
    CommandBus.clear()


def test_command_bus_dispatch_and_pipeline():
    echo_cmd = EchoCommand()
    CommandBus.register_command(echo_cmd)

    res = CommandBus.dispatch("echo", params={"message": "Hello Pipeline"}, role="owner")

    assert isinstance(res, CommandResult)
    assert res.success is True
    assert res.state == ExecutionState.COMPLETED
    assert res.data["echoed_message"] == "Hello Pipeline"
    assert res.execution_time_ms >= 0.0


def test_execution_transaction_nesting():
    tx = ExecutionTransaction()
    assert tx.correlation_id is not None
    assert tx.parent_execution_id is None

    child_tx = tx.create_nested_transaction()
    assert child_tx.correlation_id == tx.correlation_id
    assert child_tx.parent_execution_id == tx.execution_id
    assert child_tx.execution_id in tx.nested_executions


def test_unregistered_command_dispatch():
    res = CommandBus.dispatch("non_existent_cmd")
    assert res.success is False
    assert res.state == ExecutionState.FAILED
    assert "not registered" in res.error_message

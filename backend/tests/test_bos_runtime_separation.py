"""Tests for B.O.S. Core Runtime Separation (11-Stage Lifecycle)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.engine import BOSRuntimeEngine, process_message
from runtime.contracts import NormalizedRequest, BusinessIntent, RuntimeContext


def test_observation_engine():
    from runtime.observation import ObservationEngine

    req = ObservationEngine.observe(
        role="owner",
        message="status check",
        channel="command_center",
        sender_name="Vikram",
    )
    assert isinstance(req, NormalizedRequest)
    assert req.role == "owner"
    assert req.message == "status check"
    assert req.channel == "command_center"
    assert req.request_id.startswith("req_")


def test_understanding_engine():
    from runtime.observation import ObservationEngine
    from runtime.understanding import UnderstandingEngine

    req = ObservationEngine.observe(role="customer", message="hello")
    intent = UnderstandingEngine.understand(req)
    assert isinstance(intent, BusinessIntent)
    assert intent.intent_type == "customer_chat"
    assert intent.action == "chat"


def test_context_engine():
    from runtime.observation import ObservationEngine
    from runtime.understanding import UnderstandingEngine
    from runtime.context import ContextEngine

    req = ObservationEngine.observe(role="owner", message="status")
    intent = UnderstandingEngine.understand(req)
    ctx = ContextEngine.load_context(req, intent)
    assert isinstance(ctx, RuntimeContext)


def test_bos_runtime_engine_customer_flow():
    res = BOSRuntimeEngine.execute(
        role="customer",
        message="Namaste, radio station ke baare me batao.",
        sender_name="Amit",
        phone="9999999999",
    )
    assert isinstance(res, dict)
    assert "reply" in res
    assert res.get("role") == "customer"
    assert res.get("source") == "bos_runtime"


def test_bos_runtime_engine_employee_flow():
    res = BOSRuntimeEngine.execute(
        role="employee",
        message="Shift schedule check",
    )
    assert isinstance(res, dict)
    assert "Employee channel abhi active nahi hai" in res.get("reply", "")
    assert res.get("action_type") == "EMPLOYEE_STUB"


def test_process_message_entry_point():
    res = process_message(
        role="customer",
        message="hi",
    )
    assert isinstance(res, dict)
    assert "reply" in res

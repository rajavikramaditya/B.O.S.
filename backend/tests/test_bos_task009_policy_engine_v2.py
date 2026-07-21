"""Tests for TASK-009: Policy Engine v2."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.policy import (
    SecurityPolicy,
    ApprovalPolicy,
    PermissionsPolicy,
    BusinessPolicy,
    ExecutionPolicy,
    PolicyEngineV2,
)


def test_security_policy():
    res1 = SecurityPolicy.evaluate("now_playing", {})
    assert res1 == "ALLOW"

    res2 = SecurityPolicy.evaluate("raw_exec", {}, raw_text="rm -rf /")
    assert res2 == "DENY"


def test_approval_policy():
    res1 = ApprovalPolicy.evaluate("send_azuracast", {}, role="owner")
    assert res1 == "CONFIRM"

    res2 = ApprovalPolicy.evaluate("now_playing", {}, role="owner")
    assert res2 == "ALLOW"


def test_permissions_policy():
    res1 = PermissionsPolicy.evaluate("chat", role="customer")
    assert res1 == "ALLOW"

    res2 = PermissionsPolicy.evaluate("send_azuracast", role="customer")
    assert res2 == "DENY"


def test_policy_engine_v2():
    eval1 = PolicyEngineV2.evaluate("send_azuracast", {}, role="owner")
    assert eval1["status"] == "CONFIRM"
    assert eval1["require_confirmation"] is True

    eval2 = PolicyEngineV2.evaluate("chat", {}, role="customer")
    assert eval2["status"] == "ALLOW"

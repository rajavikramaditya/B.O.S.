"""Tests for TASK-003: Universal Capability Registry."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.registry import (
    CapabilityMetadata,
    UniversalCapability,
    UniversalCapabilityRegistry,
)


def test_capability_metadata_schema():
    meta = CapabilityMetadata(
        name="test_cap",
        description="Testing metadata",
        required_inputs=["input1"],
        expected_outputs=["output1"],
        required_permissions=["admin"],
        supported_adapters=["adapter1"],
        execution_strategy="async",
        retry_policy={"max_retries": 5},
    )
    d = meta.to_dict()
    assert d["name"] == "test_cap"
    assert d["execution_strategy"] == "async"
    assert d["supported_adapters"] == ["adapter1"]


def test_universal_capability_registry_defaults():
    UniversalCapabilityRegistry.initialize_defaults()
    metadata_list = UniversalCapabilityRegistry.list_metadata()
    names = [m["name"] for m in metadata_list]
    
    expected_names = [
        "messaging", "scheduling", "workflow", "knowledge", "memory",
        "contacts", "documents", "notification", "analytics", "search",
        "automation", "approval", "identity",
    ]
    for name in expected_names:
        assert name in names, f"Missing capability: {name}"


def test_resolve_capability():
    cap = UniversalCapabilityRegistry.get("messaging")
    assert cap is not None
    assert cap.name == "messaging"
    res = cap.execute_action("messaging", {"text": "hello"})
    assert res["success"] is True

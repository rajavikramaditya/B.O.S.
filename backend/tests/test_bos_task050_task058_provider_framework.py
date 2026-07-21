"""Tests for TASK-050 to TASK-058: Provider Framework."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from providers import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderLoader,
    ProviderManifest,
    ProviderResolver,
    RuntimeProviderRegistry,
)
from providers.reference import LocalEchoProvider, MemoryEchoProvider


def setup_function():
    RuntimeProviderRegistry.clear()


def test_provider_registration_and_priority_resolution():
    local_p = LocalEchoProvider("LocalEcho", priority=10)
    memory_p = MemoryEchoProvider("MemoryEcho", priority=20)

    RuntimeProviderRegistry.register(local_p)
    RuntimeProviderRegistry.register(memory_p)

    resolved = ProviderResolver.resolve("echo")
    assert resolved is not None
    assert resolved.metadata.name == "LocalEcho"


def test_provider_fallback_when_highest_disabled():
    local_p = LocalEchoProvider("LocalEcho", priority=10)
    memory_p = MemoryEchoProvider("MemoryEcho", priority=20)

    RuntimeProviderRegistry.register(local_p)
    RuntimeProviderRegistry.register(memory_p)

    RuntimeProviderRegistry.disable_provider("LocalEcho")

    resolved = ProviderResolver.resolve("echo")
    assert resolved is not None
    assert resolved.metadata.name == "MemoryEcho"


def test_provider_manifest_loading():
    manifest_data = {
        "name": "ManifestEchoProvider",
        "capability": "echo",
        "priority": 5,
        "description": "Loaded via manifest",
    }
    manifest = ProviderManifest.from_dict(manifest_data)
    provider = ProviderLoader.load_from_manifest(manifest, LocalEchoProvider)

    assert provider.metadata.name == "ManifestEchoProvider"
    assert provider.metadata.priority == 5

    res = ProviderResolver.execute_capability("echo", "ping", {"text": "Manifest Test"})
    assert res["success"] is True
    assert res["resolved_provider"] == "ManifestEchoProvider"


def test_provider_health_check():
    local_p = LocalEchoProvider("HealthEcho", priority=15)
    RuntimeProviderRegistry.register(local_p)

    health = ProviderHealth.check_health(local_p)
    assert health["is_live"] is True
    assert health["status"] in [ProviderHealthStatus.READY.value, ProviderHealthStatus.LIVE.value]

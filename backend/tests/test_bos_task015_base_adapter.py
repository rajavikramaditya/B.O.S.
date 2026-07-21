"""Tests for TASK-015: Base Adapter Architecture."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from adapters import (
    BaseAdapter,
    AdapterRequest,
    AdapterResponse,
    AdapterStatus,
    AdapterRegistry,
)


class MockAdapter(BaseAdapter):
    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> dict:
        return {"status": self.status, "healthy": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        return AdapterResponse(
            success=True,
            status=self.status,
            data={"echo_action": request.action},
        )


def test_base_adapter_contract_and_registry():
    AdapterRegistry.clear()
    adapter = MockAdapter(name="mock_whatsapp", channel_type="messaging")
    AdapterRegistry.register(adapter)

    retrieved = AdapterRegistry.get("mock_whatsapp")
    assert retrieved is not None
    assert retrieved.channel_type == "messaging"

    conn = retrieved.connect()
    assert conn is True
    assert retrieved.status == AdapterStatus.CONNECTED

    req = AdapterRequest(action="send_msg", recipient="9876543210")
    res = retrieved.execute_request(req)
    assert res.success is True
    assert res.data["echo_action"] == "send_msg"

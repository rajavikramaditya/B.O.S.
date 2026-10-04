"""Shared fixtures: an isolated platform per test with a scripted AI provider."""

import json
import os
import sys
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adapters.registry import AdapterRegistry  # noqa: E402
from capabilities.policies import CapabilityPolicyManager  # noqa: E402
from capabilities.registry import RuntimeCapabilityRegistry  # noqa: E402
from providers.base.base_provider import BaseProvider  # noqa: E402
from providers.base.provider_context import ProviderContext  # noqa: E402
from providers.base.provider_metadata import ProviderMetadata  # noqa: E402
from providers.registry import RuntimeProviderRegistry  # noqa: E402


class ScriptedAI(BaseProvider):
    """`text_generation` provider returning queued cognition results, then a plain reply."""

    def __init__(self):
        super().__init__(ProviderMetadata(name="scripted_ai", capability="text_generation", priority=1))
        self.queue: List[Dict[str, Any]] = []
        self.requests: List[Dict[str, Any]] = []

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def plan(self, steps: Optional[List[Dict[str, Any]]] = None, reply: str = "Sure.", insights=None) -> None:
        self.queue.append(
            {
                "intent_type": "test",
                "goal": "test goal",
                "summary": "test",
                "language": "English",
                "confidence": 0.9,
                "entities": [],
                "steps": [
                    {
                        "capability": s["capability"],
                        "action": s["action"],
                        "params_json": json.dumps(s.get("params", {})),
                        "title": s.get("title", f"{s['capability']}.{s['action']}"),
                        "reason": s.get("reason", "test"),
                    }
                    for s in (steps or [])
                ],
                "reply": reply,
                "insights": insights or [],
            }
        )

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.requests.append(params)
        schema = params.get("json_schema") or {}
        if schema.get("required") == ["reply"]:
            facts = json.loads(params["messages"][-1]["content"])
            return {"success": True, "provider": "scripted", "text": "", "data": {"reply": f"GROUNDED {json.dumps(facts, default=str)}"}}
        data = self.queue.pop(0) if self.queue else None
        if data is None:
            self.plan()
            data = self.queue.pop(0)
        return {"success": True, "provider": "scripted", "text": json.dumps(data), "data": data}


def _reset_registries() -> None:
    RuntimeProviderRegistry.clear()
    RuntimeCapabilityRegistry.clear()
    CapabilityPolicyManager.clear()
    AdapterRegistry.clear()


@pytest.fixture
def platform_app(tmp_path, monkeypatch):
    """A fresh B.O.S. app on a temp data dir (no scheduler, no real AI)."""
    from fastapi.testclient import TestClient

    from api.app import create_app
    from api.rate_limit import auth_limiter
    from bootstrap.settings import PlatformSettings
    from integrations.webhooks import WebhookDispatcher

    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DATABASE_URL", "MEMORY_DATABASE_URL", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BOS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(WebhookDispatcher, "synchronous", True)
    _reset_registries()
    auth_limiter.reset()
    app = create_app(PlatformSettings.from_env(), start_scheduler=False)
    with TestClient(app) as client:
        yield client
    _reset_registries()


@pytest.fixture
def ai(platform_app) -> ScriptedAI:
    provider = ScriptedAI()
    RuntimeProviderRegistry.register(provider)
    provider.initialize(ProviderContext(provider_id="scripted_ai"))
    return provider


@pytest.fixture
def owner(platform_app) -> Dict[str, str]:
    res = platform_app.post("/api/setup/owner", json={"name": "Asha", "email": "asha@example.com", "password": "correct-horse"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}

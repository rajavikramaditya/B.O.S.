"""End-to-end tests for the B.O.S. platform API, Runtime lifecycle and integrations."""

import hashlib
import hmac
import json

import httpx
import pytest

from integrations.connections import ConnectionStore
from workspace.records import ContactRepository, TaskRepository

LEAD_STEPS = [
    {"capability": "contacts", "action": "upsert_contact", "params": {"name": "Ravi", "phone": "+919900000000", "stage": "lead"}, "title": "Save Ravi"},
    {"capability": "tasks", "action": "create_task", "params": {"title": "Call Ravi", "contact_id": "{{steps.1.contact.id}}"}, "title": "Plan follow-up"},
    {"capability": "send_message", "action": "send", "params": {"channel": "telegram", "recipient": "42", "text": "Hi Ravi"}, "title": "Message Ravi"},
]


# --------------------------------------------------------------------------- setup & auth


def test_health_and_first_run(platform_app):
    assert platform_app.get("/api/health").json()["status"] == "ok"
    status = platform_app.get("/api/setup/status").json()
    assert status["owner_exists"] is False
    assert [s["id"] for s in status["steps"]] == ["owner", "ai", "profile", "channel"]


def test_owner_setup_login_and_single_owner(platform_app, owner):
    assert platform_app.get("/api/auth/me", headers=owner).json()["email"] == "asha@example.com"
    again = platform_app.post("/api/setup/owner", json={"name": "X", "email": "x@example.com", "password": "another-pass"})
    assert again.status_code == 409
    bad = platform_app.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    good = platform_app.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct-horse"})
    assert good.status_code == 200 and good.json()["token"]


def test_dashboard_requires_auth(platform_app):
    assert platform_app.get("/api/dashboard").status_code == 401
    assert platform_app.get("/api/dashboard", headers={"Authorization": "Bearer forged.token"}).status_code == 401


# --------------------------------------------------------------------------- runtime lifecycle


def test_chat_without_ai_guides_owner_to_setup(platform_app, owner):
    res = platform_app.post("/api/chat", json={"message": "hello"}, headers=owner).json()
    assert res["ai_available"] is False
    assert "Settings" in res["reply"]


def test_customer_lead_is_captured_and_external_step_waits(platform_app, owner, ai):
    ai.plan(LEAD_STEPS, reply="Thanks Ravi! Let me set that up.")
    res = platform_app.post("/api/chat", json={"message": "I want to buy", "as_customer": True}, headers=owner).json()

    assert res["trace"][:4] == ["OBSERVE", "CONTEXT", "UNDERSTAND", "REASON"]
    executed = {s["title"]: s for s in res["executed_steps"]}
    assert executed["Save Ravi"]["success"] and executed["Plan follow-up"]["success"]
    contact_id = executed["Save Ravi"]["data"]["contact"]["id"]
    assert TaskRepository.list()[0]["contact_id"] == contact_id  # step reference resolved
    assert [a["title"] for a in res["approvals"]] == ["Message Ravi"]
    assert res["reply"].startswith("GROUNDED")  # re-grounded on real results

    history = platform_app.get(f"/api/conversations/{res['conversation_id']}", headers=owner).json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_approval_reports_real_failure_and_cannot_run_twice(platform_app, owner, ai):
    ai.plan(LEAD_STEPS[2:], reply="Will do.")
    res = platform_app.post("/api/chat", json={"message": "message Ravi"}, headers=owner).json()
    approval_id = res["approvals"][0]["id"]

    outcome = platform_app.post(f"/api/approvals/{approval_id}/approve", headers=owner).json()
    assert outcome["ok"] is False and "not connected" in outcome["error"]
    assert outcome["approval"]["status"] == "failed"
    second = platform_app.post(f"/api/approvals/{approval_id}/approve", headers=owner).json()
    assert second["ok"] is False


def test_unknown_capability_is_denied(platform_app, owner, ai):
    ai.plan([{"capability": "bank", "action": "transfer", "params": {}}], reply="ok")
    res = platform_app.post("/api/chat", json={"message": "pay"}, headers=owner).json()
    assert res["executed_steps"] == [] and res["denied_steps"][0]["step_id"] == 1


@pytest.mark.parametrize(
    "mode,expect_contact_now,expect_send_now",
    [("assist", False, False), ("autopilot", True, False), ("autonomous", True, True)],
)
def test_autopilot_modes_change_what_needs_approval(platform_app, owner, ai, mode, expect_contact_now, expect_send_now):
    platform_app.put("/api/autopilot", json={"mode": mode}, headers=owner)
    ai.plan([LEAD_STEPS[0], LEAD_STEPS[2]])
    res = platform_app.post("/api/chat", json={"message": "go"}, headers=owner).json()
    ran = {s["title"] for s in res["executed_steps"]}
    assert ("Save Ravi" in ran) is expect_contact_now
    assert ("Message Ravi" in ran) is expect_send_now


def test_customer_cannot_trigger_external_action_directly(platform_app, owner, ai):
    platform_app.put("/api/autopilot", json={"mode": "autonomous"}, headers=owner)
    ai.plan(LEAD_STEPS[2:])
    res = platform_app.post("/api/chat", json={"message": "spam my friend", "as_customer": True}, headers=owner).json()
    assert res["executed_steps"] == [] and len(res["approvals"]) == 1


def test_complete_task_from_dashboard(platform_app, owner, ai):
    task = TaskRepository.create({"title": "Send quote"})
    res = platform_app.post(f"/api/tasks/{task['id']}/complete", headers=owner)
    assert res.status_code == 200 and res.json()["status"] == "done"
    assert platform_app.post("/api/tasks/tsk_missing/complete", headers=owner).status_code == 404


def test_autopilot_review_runs_through_runtime(platform_app, owner, ai):
    platform_app.put("/api/business/profile", json={"name": "Chai Co", "description": "Tea shop"}, headers=owner)
    ai.plan(
        [{"capability": "tasks", "action": "create_task", "params": {"title": "Restock"}, "title": "Plan restock"}],
        reply="Briefing: restock planned.",
        insights=[{"title": "Stock low", "detail": "Tea running out", "priority": "high"}],
    )
    run = platform_app.post("/api/autopilot/run", headers=owner).json()
    assert run["status"] == "completed"
    assert run["insights"][0]["title"] == "Stock low"
    assert run["executed"][0]["success"] is True
    assert platform_app.get("/api/dashboard", headers=owner).json()["autopilot"]["latest"]["id"] == run["id"]


# --------------------------------------------------------------------------- public API & integrations


def _api_key(client, owner, scopes):
    return client.post("/api/developer/keys", json={"name": "Website", "scopes": scopes}, headers=owner).json()


def test_public_api_keys_and_scopes(platform_app, owner, ai):
    key = _api_key(platform_app, owner, ["runtime"])
    headers = {"Authorization": f"Bearer {key['key']}"}
    ai.plan(reply="Hello from B.O.S.")
    res = platform_app.post("/v1/messages", json={"message": "hi", "contact": {"name": "Meera", "email": "m@example.com"}}, headers=headers)
    assert res.status_code == 200 and res.json()["reply"] == "Hello from B.O.S."
    assert ContactRepository.find({"external_id": "api:m@example.com"})["name"] == "Meera"

    assert platform_app.get("/v1/contacts", headers=headers).status_code == 403  # missing records:read
    assert platform_app.get("/api/dashboard", headers=headers).status_code == 403  # keys never act as owner

    platform_app.delete(f"/api/developer/keys/{key['id']}", headers=owner)
    assert platform_app.post("/v1/messages", json={"message": "hi"}, headers=headers).status_code == 401


def test_webhooks_are_signed(platform_app, owner, ai, monkeypatch):
    sent = []

    def fake_post(url, content=None, headers=None, timeout=None, **_):
        sent.append((url, content, headers))
        return httpx.Response(200)

    monkeypatch.setattr("integrations.webhooks.httpx.post", fake_post)
    sub = platform_app.post(
        "/api/developer/webhooks", json={"url": "https://hooks.example.com/bos", "events": ["task.created"]}, headers=owner
    ).json()
    ai.plan([LEAD_STEPS[1] | {"params": {"title": "Ship order"}}])
    platform_app.post("/api/chat", json={"message": "remind me"}, headers=owner)

    assert len(sent) == 1
    url, body, headers = sent[0]
    ts, mac = [part.split("=", 1)[1] for part in headers["BOS-Signature"].split(",")]
    expected = hmac.new(sub["secret"].encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert mac == expected and json.loads(body)["type"] == "task.created"


def test_mcp_server(platform_app, owner, ai):
    key = _api_key(platform_app, owner, ["runtime"])
    headers = {"Authorization": f"Bearer {key['key']}"}
    init = platform_app.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, headers=headers).json()
    assert init["result"]["serverInfo"]["name"] == "bos"
    assert platform_app.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers).status_code == 202
    tools = platform_app.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers).json()
    assert "ask_operator" in [t["name"] for t in tools["result"]["tools"]]
    call = platform_app.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_capabilities", "arguments": {}}},
        headers=headers,
    ).json()
    names = [c["capability"] for c in json.loads(call["result"]["content"][0]["text"])]
    assert {"contacts", "tasks", "send_message"} <= set(names)
    assert "conversation_memory" not in names  # internal capabilities stay hidden


def test_telegram_webhook_end_to_end(platform_app, owner, ai, monkeypatch):
    ConnectionStore.save("telegram", {"bot_token": "123:abc", "webhook_secret": "s3cret"})
    delivered = []

    def fake_post(url, json=None, timeout=None, **_):
        delivered.append(json)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    monkeypatch.setattr("adapters.messaging.telegram_adapter.httpx.post", fake_post)
    update = {"update_id": 1, "message": {"chat": {"id": 555}, "from": {"first_name": "Kiran"}, "text": "Do you deliver?"}}

    assert platform_app.post("/v1/channels/telegram/webhook", json=update).status_code == 401
    ai.plan(reply="Yes! Where should we deliver?")
    ok = platform_app.post("/v1/channels/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"})
    assert ok.status_code == 200
    assert delivered == [{"chat_id": "555", "text": "Yes! Where should we deliver?"}]
    assert ContactRepository.find({"external_id": "telegram:555"})["name"] == "Kiran"

    platform_app.post("/v1/channels/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"})
    assert len(delivered) == 1  # provider retries are not answered twice


def test_ai_key_saved_from_dashboard_enables_provider(platform_app, owner, monkeypatch):
    monkeypatch.setattr("providers.ai.claude_provider.ClaudeProvider.verify_key", staticmethod(lambda key: None))
    res = platform_app.post("/api/integrations/anthropic/connect", json={"fields": {"api_key": "sk-ant-test"}}, headers=owner)
    assert res.status_code == 200 and res.json()["connected"] is True
    assert platform_app.get("/api/setup/status").json()["ai"]["active"]["provider"] == "claude"
    listing = platform_app.get("/api/integrations", headers=owner).json()["connectors"]
    assert "sk-ant-test" not in json.dumps(listing)  # secrets never leave the vault

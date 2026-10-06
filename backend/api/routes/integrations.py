"""B.O.S. Integration Routes v1.0

Connect AI models and channels, manage API keys and webhook subscriptions.
"""

import secrets
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from adapters.messaging.telegram_adapter import TelegramAdapter
from bootstrap.platform import Platform
from integrations.api_keys import DEFAULT_SCOPES, SCOPES, ApiKeyService
from integrations.catalog import CONNECTORS, get_connector
from integrations.connections import ConnectionStore
from integrations.webhooks import EVENT_TYPES, WebhookDispatcher
from workspace.activity import ActivityLog

from ..security import require_owner

router = APIRouter(prefix="/api", tags=["Integrations"], dependencies=[Depends(require_owner)])


class ConnectBody(BaseModel):
    fields: Dict[str, str] = Field(default_factory=dict)


class ApiKeyBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: List[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))


class WebhookBody(BaseModel):
    url: HttpUrl
    events: List[str] = Field(default_factory=lambda: ["*"])
    description: str = ""


def _base_url() -> str:
    return Platform.settings.public_base_url if Platform.settings else ""


def _status(connector: Dict[str, Any]) -> Dict[str, Any]:
    cid = connector["id"]
    view = dict(connector)
    if connector["kind"] == "builtin":
        view["connected"] = True
    elif connector["kind"] == "ai":
        view["connected"] = Platform.ai_providers[cid].is_configured()
        view["model"] = Platform.ai_providers[cid].model
    else:
        view["connected"] = ConnectionStore.is_connected(cid)
        view["meta"] = ConnectionStore.meta(cid)
    if connector.get("inbound"):
        view["inbound_url"] = f"{_base_url()}{connector['inbound']}" if _base_url() else connector["inbound"]
    return view


@router.get("/integrations")
def list_integrations() -> Dict[str, Any]:
    return {"connectors": [_status(c) for c in CONNECTORS], "public_base_url": _base_url()}


@router.post("/integrations/{connector_id}/connect")
def connect(connector_id: str, body: ConnectBody) -> Dict[str, Any]:
    connector = get_connector(connector_id)
    if connector is None or connector["kind"] == "builtin":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown connector.")
    values = {f["key"]: (body.fields.get(f["key"]) or "").strip() for f in connector["fields"]}
    required = [f["key"] for f in connector["fields"] if f["key"] != "port"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Please fill in: {', '.join(missing)}")

    meta: Dict[str, Any] = {}
    if connector["kind"] == "ai":
        problem = type(Platform.ai_providers[connector_id]).verify_key(values["api_key"])
        if problem:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    elif connector_id == "telegram":
        meta = _connect_telegram(values)
    elif connector_id == "whatsapp":
        meta = {"webhook_url": f"{_base_url()}/v1/channels/whatsapp/webhook" if _base_url() else "Set PUBLIC_BASE_URL first"}

    ConnectionStore.save(connector_id, values, meta)
    if connector["kind"] == "ai":
        Platform.refresh_ai_providers()
    ActivityLog.record("integration.connected", f"{connector['name']} connected")
    return _status(connector)


def _connect_telegram(values: Dict[str, str]) -> Dict[str, Any]:
    try:
        me = TelegramAdapter.verify_token(values["bot_token"])
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach Telegram. Please try again.")
    if not me.get("ok"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Telegram rejected this bot token.")
    values["webhook_secret"] = secrets.token_urlsafe(24)
    meta: Dict[str, Any] = {"bot_username": me["result"].get("username"), "webhook": "pending"}
    if _base_url().startswith("https://"):
        registered = TelegramAdapter.register_webhook(
            values["bot_token"], f"{_base_url()}/v1/channels/telegram/webhook", values["webhook_secret"]
        )
        meta["webhook"] = "active" if registered.get("ok") else f"failed: {registered.get('description')}"
    else:
        meta["webhook"] = "Set PUBLIC_BASE_URL to an https address so Telegram can reach B.O.S."
    return meta


@router.delete("/integrations/{connector_id}")
def disconnect(connector_id: str) -> Dict[str, Any]:
    connector = get_connector(connector_id)
    if connector is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown connector.")
    removed = ConnectionStore.remove(connector_id)
    if connector["kind"] == "ai":
        Platform.refresh_ai_providers()
    if removed:
        ActivityLog.record("integration.disconnected", f"{connector['name']} disconnected")
    return _status(connector)


@router.get("/developer/keys")
def list_keys() -> Dict[str, Any]:
    return {"keys": ApiKeyService.list(), "scopes": list(SCOPES), "default_scopes": list(DEFAULT_SCOPES)}


@router.post("/developer/keys")
def create_key(body: ApiKeyBody) -> Dict[str, Any]:
    key = ApiKeyService.create(body.name, body.scopes)
    ActivityLog.record("developer.key_created", f"API key '{body.name}' created")
    return key


@router.delete("/developer/keys/{key_id}")
def revoke_key(key_id: str) -> Dict[str, Any]:
    if not ApiKeyService.revoke(key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found.")
    return {"revoked": True}


@router.get("/developer/webhooks")
def list_webhooks() -> Dict[str, Any]:
    return {"webhooks": WebhookDispatcher.list(), "events": EVENT_TYPES, "deliveries": WebhookDispatcher.recent_deliveries(20)}


@router.post("/developer/webhooks")
def create_webhook(body: WebhookBody) -> Dict[str, Any]:
    events = [e for e in body.events if e == "*" or e in EVENT_TYPES or e.startswith("custom.")] or ["*"]
    sub = WebhookDispatcher.subscribe(str(body.url), events, body.description)
    ActivityLog.record("developer.webhook_created", f"Webhook added for {body.url.host}")
    return sub


@router.delete("/developer/webhooks/{subscription_id}")
def delete_webhook(subscription_id: str) -> Dict[str, Any]:
    if not WebhookDispatcher.unsubscribe(subscription_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    return {"deleted": True}

"""B.O.S. Channel Webhook Routes v1.0

Inbound customer messages from Telegram and WhatsApp. Requests are verified,
acknowledged immediately, and processed in the background through the Runtime.
Payload parsing here is protocol parsing, not language understanding.
"""

import hashlib
import hmac
import json
import threading
from collections import OrderedDict
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status

from gateway.runtime_gateway import RuntimeGateway
from integrations.connections import ConnectionStore

router = APIRouter(prefix="/v1/channels", tags=["Channels"])


class _SeenMessages:
    """Bounded memory of processed message ids so provider retries are not answered twice."""

    def __init__(self, size: int = 2000):
        self._ids: "OrderedDict[str, None]" = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def first_time(self, key: str) -> bool:
        with self._lock:
            if key in self._ids:
                return False
            self._ids[key] = None
            if len(self._ids) > self._size:
                self._ids.popitem(last=False)
            return True


seen = _SeenMessages()

# Real Telegram / WhatsApp updates are a few KB; anything far larger is refused before hashing or parsing.
MAX_WEBHOOK_BYTES = 256 * 1024


async def _read_body(request: Request) -> bytes:
    """Read the request body, refusing it as soon as it exceeds MAX_WEBHOOK_BYTES."""
    too_large = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Payload too large.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_WEBHOOK_BYTES:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BYTES:
            raise too_large
    return bytes(body)


def _parse_json(raw: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON.")
    return data if isinstance(data, dict) else {}


def handle_customer_message(*, channel: str, external_id: str, name: str, text: str, phone: str = "") -> None:
    contact_id = RuntimeGateway.identify_contact(channel=channel, external_id=external_id, name=name, phone=phone)
    result = RuntimeGateway.submit(
        role="customer",
        message=text,
        channel=channel,
        conversation_id=f"{channel}:{external_id}",
        sender_name=name or "Customer",
        actor_ref=contact_id,
        source=channel,
    )
    RuntimeGateway.deliver_reply(channel=channel, recipient=external_id, text=result.get("reply", ""))


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    creds = ConnectionStore.credentials("telegram")
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not creds.get("webhook_secret") or not hmac.compare_digest(secret, creds["webhook_secret"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret.")
    update = _parse_json(await _read_body(request))
    message = update.get("message") or {}
    text = message.get("text")
    chat_id = str((message.get("chat") or {}).get("id") or "")
    if not text or not chat_id or not seen.first_time(f"tg:{update.get('update_id')}"):
        return {"ok": True}
    sender = message.get("from") or {}
    name = " ".join(p for p in (sender.get("first_name"), sender.get("last_name")) if p) or sender.get("username") or ""
    background.add_task(handle_customer_message, channel="telegram", external_id=chat_id, name=name, text=text)
    return {"ok": True}


@router.get("/whatsapp/webhook")
def whatsapp_verify(request: Request) -> Response:
    params = request.query_params
    expected = ConnectionStore.credentials("whatsapp").get("verify_token", "")
    if params.get("hub.mode") == "subscribe" and expected and hmac.compare_digest(params.get("hub.verify_token", ""), expected):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed.")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    creds = ConnectionStore.credentials("whatsapp")
    if not creds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WhatsApp is not connected.")
    if not creds.get("app_secret"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Add the WhatsApp app secret so incoming messages can be verified.")
    signature = request.headers.get("x-hub-signature-256", "")
    if not signature.startswith("sha256="):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature.")
    raw = await _read_body(request)
    expected = "sha256=" + hmac.new(creds["app_secret"].encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature.")
    payload = _parse_json(raw)
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts") or []}
            for msg in value.get("messages") or []:
                if msg.get("type") != "text" or not seen.first_time(f"wa:{msg.get('id')}"):
                    continue
                sender = str(msg.get("from") or "")
                background.add_task(
                    handle_customer_message,
                    channel="whatsapp",
                    external_id=sender,
                    name=names.get(sender, ""),
                    text=(msg.get("text") or {}).get("body", ""),
                    phone=f"+{sender}" if sender else "",
                )
    return {"ok": True}

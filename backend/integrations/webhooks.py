"""B.O.S. Outbound Webhooks v1.0

Delivers platform events to subscribed URLs, signed Stripe-style so receivers
can verify authenticity:

    BOS-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
"""

import hashlib
import hmac
import json
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select

from workspace.database import WorkspaceDatabase
from workspace.models import WebhookDelivery, WebhookSubscription
from workspace.vault import WorkspaceVault

EVENT_TYPES = [
    "conversation.message.received",
    "conversation.reply.sent",
    "contact.saved",
    "task.created",
    "task.completed",
    "approval.requested",
    "approval.decided",
    "action.executed",
    "autopilot.briefing.ready",
]

RETRY_DELAYS = (0, 2, 10)


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def subscription_to_dict(s: WebhookSubscription) -> Dict[str, Any]:
    return {
        "id": s.id,
        "url": s.url,
        "events": s.events or [],
        "active": s.active,
        "description": s.description,
        "created_at": s.created_at,
    }


class WebhookDispatcher:
    """Signs and delivers events in the background with retries."""

    _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bos-webhooks")
    synchronous = False  # tests flip this to deliver inline

    @classmethod
    def subscribe(cls, url: str, events: List[str], description: str = "") -> Dict[str, Any]:
        secret = f"whsec_{secrets.token_urlsafe(24)}"
        with WorkspaceDatabase.session() as db:
            sub = WebhookSubscription(
                url=url,
                events=events or ["*"],
                secret_encrypted=WorkspaceVault.encrypt(secret),
                description=description,
            )
            db.add(sub)
            db.flush()
            out = subscription_to_dict(sub)
        out["secret"] = secret  # shown once
        return out

    @classmethod
    def unsubscribe(cls, subscription_id: str) -> bool:
        with WorkspaceDatabase.session() as db:
            sub = db.get(WebhookSubscription, subscription_id)
            if sub is None:
                return False
            db.delete(sub)
            return True

    @classmethod
    def list(cls) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            return [subscription_to_dict(s) for s in db.scalars(select(WebhookSubscription)).all()]

    @classmethod
    def recent_deliveries(cls, limit: int = 30) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            rows = db.scalars(select(WebhookDelivery).order_by(WebhookDelivery.id.desc()).limit(limit)).all()
            return [
                {
                    "subscription_id": r.subscription_id,
                    "event": r.event,
                    "success": r.success,
                    "status_code": r.status_code,
                    "error": r.error,
                    "attempted_at": r.attempted_at,
                }
                for r in rows
            ]

    @classmethod
    def publish(cls, event: str, data: Dict[str, Any]) -> int:
        """Queue delivery to every matching subscription; returns how many were queued."""
        envelope = {
            "id": f"evt_{uuid.uuid4().hex[:20]}",
            "type": event,
            "created_at": int(time.time()),
            "data": data,
        }
        targets = []
        with WorkspaceDatabase.session() as db:
            for sub in db.scalars(select(WebhookSubscription).where(WebhookSubscription.active.is_(True))).all():
                events = sub.events or ["*"]
                if "*" in events or event in events:
                    targets.append((sub.id, sub.url, WorkspaceVault.decrypt(sub.secret_encrypted)))
        for target in targets:
            if cls.synchronous:
                cls._deliver(*target, envelope)
            else:
                cls._pool.submit(cls._deliver, *target, envelope)
        return len(targets)

    @classmethod
    def _deliver(cls, subscription_id: str, url: str, secret: str, envelope: Dict[str, Any]) -> None:
        body = json.dumps(envelope, default=str).encode()
        status: Optional[int] = None
        error = ""
        for delay in RETRY_DELAYS:
            if delay and not cls.synchronous:
                time.sleep(delay)
            ts = int(time.time())
            try:
                resp = httpx.post(
                    url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "BOS-Webhooks/1.0",
                        "BOS-Event": envelope["type"],
                        "BOS-Signature": sign(secret, ts, body),
                    },
                    timeout=10.0,
                )
                status = resp.status_code
                if 200 <= status < 300:
                    error = ""
                    break
                error = f"HTTP {status}"
            except httpx.HTTPError as ex:
                error = str(ex) or ex.__class__.__name__
        with WorkspaceDatabase.session() as db:
            db.add(
                WebhookDelivery(
                    subscription_id=subscription_id,
                    event=envelope["type"],
                    success=not error,
                    status_code=status,
                    error=error[:500],
                )
            )

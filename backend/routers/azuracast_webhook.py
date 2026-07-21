"""Inbound AzuraCast webhooks — system kaan for fast stream/media truth."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/azuracast", tags=["azuracast-webhook"])


@router.post("/webhook")
async def azuracast_webhook(
    request: Request,
    x_neena_webhook_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    from services.broadcast.azura_events import record_event, webhook_secret

    expected = webhook_secret()
    if expected:
        provided = (x_neena_webhook_secret or "").strip()
        if not provided and authorization:
            # Allow "Bearer <secret>"
            auth = authorization.strip()
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip()
            else:
                provided = auth
        if provided != expected:
            raise HTTPException(status_code=401, detail="invalid_webhook_secret")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {"raw": str(body)[:500]}
    entry = record_event(body)
    logger.info("azura webhook type=%s title=%s", entry.get("type"), entry.get("title"))
    return {"ok": True, "recorded": True, "type": entry.get("type"), "title": entry.get("title")}


@router.get("/events/recent")
def azuracast_recent_events(limit: int = 5) -> dict[str, Any]:
    """Owner/CC debug — recent webhook facts (no secrets)."""
    from services.broadcast.azura_events import latest_events, webhook_secret

    return {
        "ok": True,
        "webhook_secret_configured": bool(webhook_secret()),
        "events": latest_events(limit=limit),
    }

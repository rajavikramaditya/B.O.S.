"""M5 — Reusable owner WhatsApp notifier.

Used to push server-initiated messages (e.g. finished background-job results)
to the owner's WhatsApp via the local Node.js gateway. Best-effort and fully
guarded: never raises into the caller, short timeout so it cannot block worker
threads or request handlers.
"""
from __future__ import annotations

import logging
import os

import requests

from services.cockpit.runtime_controller import get_whatsapp_gateway_url
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)


def get_owner_digits() -> str:
    owner_raw = os.environ.get("OWNER_WHATSAPP_NUMBER", "").strip()
    return "".join(c for c in owner_raw if c.isdigit())


def notify_owner(message: str) -> bool:
    """Send a WhatsApp message to the owner. Returns True on success, else False."""
    if not message:
        return False
    owner_digits = get_owner_digits()
    if not owner_digits:
        logger.info("[OwnerNotifier] OWNER_WHATSAPP_NUMBER not set; skipping push.")
        return False
    try:
        gateway_url = get_whatsapp_gateway_url("send-message")
        res = requests.post(
            gateway_url,
            json={"phone": owner_digits, "message": message},
            timeout=5.0,
            verify=get_ssl_verify(),
        )
        if res.status_code == 200:
            return True
        logger.warning("[OwnerNotifier] Gateway returned %s", res.status_code)
    except Exception as exc:  # pragma: no cover - network best-effort
        logger.warning("[OwnerNotifier] Failed to push owner WhatsApp: %s", exc)
    return False


__all__ = ["notify_owner", "get_owner_digits"]

"""B.O.S. WhatsApp Messaging Adapter v1.0

Delivers messages through the WhatsApp Business Cloud API (Meta).
Credentials: {access_token, phone_number_id}
"""

from typing import Any, Dict, Optional

import httpx

from .channel_adapter import ChannelAdapter, CredentialsResolver

GRAPH_API = "https://graph.facebook.com/v21.0"


class WhatsAppAdapter(ChannelAdapter):
    required_fields = ("access_token", "phone_number_id")

    def __init__(self, name: str = "whatsapp", credentials: Optional[CredentialsResolver] = None):
        super().__init__(name=name, credentials=credentials)

    def deliver(self, creds: Dict[str, Any], recipient: str, text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = httpx.post(
            f"{GRAPH_API}/{creds['phone_number_id']}/messages",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            json={
                "messaging_product": "whatsapp",
                "to": recipient.lstrip("+"),
                "type": "text",
                "text": {"body": text[:4096]},
            },
            timeout=20.0,
        )
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code >= 300:
            raise RuntimeError(body.get("error", {}).get("message") or f"HTTP {resp.status_code}")
        messages = body.get("messages") or [{}]
        return {"provider_ref": str(messages[0].get("id", ""))}

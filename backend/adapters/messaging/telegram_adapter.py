"""B.O.S. Telegram Messaging Adapter v1.0

Delivers messages through the Telegram Bot API.
Credentials: {bot_token}
"""

from typing import Any, Dict, Optional

import httpx

from .channel_adapter import ChannelAdapter, CredentialsResolver

TELEGRAM_API = "https://api.telegram.org"


class TelegramAdapter(ChannelAdapter):
    required_fields = ("bot_token",)

    def __init__(self, name: str = "telegram", credentials: Optional[CredentialsResolver] = None):
        super().__init__(name=name, credentials=credentials)

    def deliver(self, creds: Dict[str, Any], recipient: str, text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = httpx.post(
            f"{TELEGRAM_API}/bot{creds['bot_token']}/sendMessage",
            json={"chat_id": recipient, "text": text[:4096]},
            timeout=20.0,
        )
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code != 200 or not body.get("ok"):
            raise RuntimeError(body.get("description") or f"HTTP {resp.status_code}")
        return {"provider_ref": str(body.get("result", {}).get("message_id", ""))}

    @staticmethod
    def register_webhook(bot_token: str, url: str, secret_token: str) -> Dict[str, Any]:
        resp = httpx.post(
            f"{TELEGRAM_API}/bot{bot_token}/setWebhook",
            json={"url": url, "secret_token": secret_token, "allowed_updates": ["message"]},
            timeout=20.0,
        )
        return resp.json()

    @staticmethod
    def verify_token(bot_token: str) -> Dict[str, Any]:
        resp = httpx.get(f"{TELEGRAM_API}/bot{bot_token}/getMe", timeout=15.0)
        return resp.json()

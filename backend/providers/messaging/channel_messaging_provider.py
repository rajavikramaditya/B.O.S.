"""B.O.S. Channel Messaging Provider v1.0

`messaging` provider that delivers through the AdapterRouter to the
connected channel adapter (Telegram, WhatsApp, Email, ...).

Actions:
    send      {channel, recipient, text, subject?}
    notify    alias of send
    broadcast {channel, recipients: [..], text}
"""

from typing import Any, Dict

from adapters.router import AdapterRouter

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata

MESSAGING = "messaging"


class ChannelMessagingProvider(BaseProvider):
    def __init__(self, priority: int = 10):
        super().__init__(
            ProviderMetadata(
                name="channel_messaging",
                capability=MESSAGING,
                priority=priority,
                description="Delivers messages through connected channel adapters.",
            )
        )

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        channel = str(params.get("channel") or "")
        if not channel:
            return {"success": False, "error": "channel is required (e.g. telegram, whatsapp, email)."}
        payload = {"text": params.get("text") or params.get("message") or "", "subject": params.get("subject")}

        if action == "broadcast":
            results = [self._send(channel, str(r), payload) for r in params.get("recipients") or []]
            sent = sum(1 for r in results if r["success"])
            return {"success": sent > 0, "sent": sent, "failed": len(results) - sent, "results": results}
        if action in ("send", "notify"):
            return self._send(channel, str(params.get("recipient") or ""), payload)
        return {"success": False, "error": f"Unsupported messaging action '{action}'."}

    @staticmethod
    def _send(channel: str, recipient: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = AdapterRouter.route_action("send", channel=channel, recipient=recipient, payload=payload)
        return {
            "success": resp.success,
            "channel": channel,
            "recipient": recipient,
            "data": resp.data,
            "error": resp.error_message,
        }

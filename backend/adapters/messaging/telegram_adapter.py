"""B.O.S. Telegram Messaging Adapter v0.1

Adapter connecting platform messaging capabilities to Telegram Bot API.
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class TelegramAdapter(BaseAdapter):
    """Adapter for Telegram messaging integration."""

    def __init__(self, name: str = "telegram"):
        super().__init__(name=name, channel_type="messaging")

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"adapter": self.name, "status": self.status, "reachable": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        chat_id = request.recipient
        msg = request.payload.get("text") or request.payload.get("message", "")

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "telegram",
                "chat_id": chat_id,
                "sent_message": msg,
                "provider_ref": f"tg_msg_{request.request_id}",
            },
        )

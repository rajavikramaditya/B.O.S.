"""B.O.S. WhatsApp Messaging Adapter v0.1

Adapter connecting platform messaging capabilities to WhatsApp gateway services.
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class WhatsAppAdapter(BaseAdapter):
    """Adapter for WhatsApp messaging integration."""

    def __init__(self, name: str = "whatsapp"):
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
        recipient = request.recipient
        msg = request.payload.get("text") or request.payload.get("message", "")

        # Adapter translation logic
        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "whatsapp",
                "recipient": recipient,
                "sent_message": msg,
                "provider_ref": f"wa_msg_{request.request_id}",
            },
        )

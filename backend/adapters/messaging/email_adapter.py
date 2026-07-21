"""B.O.S. Email Messaging Adapter v0.1

Adapter connecting platform messaging capabilities to SMTP / Email providers.
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class EmailAdapter(BaseAdapter):
    """Adapter for Email integration."""

    def __init__(self, name: str = "email"):
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
        email_to = request.recipient
        subject = request.payload.get("subject", "Notification")
        body = request.payload.get("text") or request.payload.get("body", "")

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "email",
                "email_to": email_to,
                "subject": subject,
                "sent_body": body,
                "provider_ref": f"email_msg_{request.request_id}",
            },
        )

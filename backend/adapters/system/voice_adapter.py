"""B.O.S. Voice Adapter v0.1

Adapter connecting platform voice capabilities to SIP / Twilio voice gateways.
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class VoiceAdapter(BaseAdapter):
    """Adapter for Voice calls and audio streaming integration."""

    def __init__(self, name: str = "voice"):
        super().__init__(name=name, channel_type="voice")

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"adapter": self.name, "status": self.status, "reachable": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        phone = request.recipient
        audio_url = request.payload.get("audio_url", "")

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "voice",
                "recipient": phone,
                "audio_url": audio_url,
                "call_id": f"call_{request.request_id}",
            },
        )

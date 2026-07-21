"""B.O.S. Calendar Adapter v0.1

Adapter connecting platform scheduling capabilities to Google/Outlook Calendar.
"""

from typing import Any, Dict
from ..base_adapter import BaseAdapter
from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class CalendarAdapter(BaseAdapter):
    """Adapter for Calendar and scheduling integration."""

    def __init__(self, name: str = "calendar"):
        super().__init__(name=name, channel_type="scheduling")

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"adapter": self.name, "status": self.status, "reachable": True}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        title = request.payload.get("event_title") or request.payload.get("title", "Meeting")
        event_time = request.payload.get("time", "now")

        return AdapterResponse(
            success=True,
            status=self.status,
            data={
                "channel": "calendar",
                "event_title": title,
                "time": event_time,
                "event_id": f"cal_evt_{request.request_id}",
            },
        )

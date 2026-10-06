"""B.O.S. Channel Adapter Base v1.0

Shared behaviour for messaging adapters whose credentials come from a
connected integration. An adapter without credentials reports itself as
disconnected and never pretends a message was delivered.
"""

from typing import Any, Callable, Dict, Optional

from ..adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus
from ..base_adapter import BaseAdapter

CredentialsResolver = Callable[[], Dict[str, Any]]


class ChannelAdapter(BaseAdapter):
    """Messaging adapter with lazily resolved credentials."""

    required_fields: tuple = ()

    def __init__(self, name: str, credentials: Optional[CredentialsResolver] = None):
        super().__init__(name=name, channel_type="messaging")
        self._credentials = credentials or (lambda: {})

    def credentials(self) -> Dict[str, Any]:
        try:
            return self._credentials() or {}
        except Exception:
            return {}

    def is_configured(self) -> bool:
        creds = self.credentials()
        return all(creds.get(f) for f in self.required_fields)

    def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED if self.is_configured() else AdapterStatus.DISCONNECTED
        return self.status == AdapterStatus.CONNECTED

    def disconnect(self) -> bool:
        self.status = AdapterStatus.DISCONNECTED
        return True

    def health_check(self) -> Dict[str, Any]:
        configured = self.is_configured()
        return {"adapter": self.name, "status": "CONNECTED" if configured else "DISCONNECTED", "configured": configured}

    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        creds = self.credentials()
        missing = [f for f in self.required_fields if not creds.get(f)]
        if missing:
            return AdapterResponse(
                success=False,
                status=AdapterStatus.DISCONNECTED,
                error_message=f"{self.name} is not connected (missing: {', '.join(missing)}).",
            )
        text = str(request.payload.get("text") or request.payload.get("message") or "")
        if not request.recipient or not text:
            return AdapterResponse(success=False, status=AdapterStatus.FAILED, error_message="recipient and text are required.")
        try:
            data = self.deliver(creds, request.recipient, text, request.payload)
        except Exception as ex:
            return AdapterResponse(success=False, status=AdapterStatus.FAILED, error_message=f"{self.name} delivery failed: {ex}")
        return AdapterResponse(success=True, status=AdapterStatus.CONNECTED, data={"channel": self.name, "recipient": request.recipient, **data})

    def deliver(self, creds: Dict[str, Any], recipient: str, text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send the message through the external system; raise on failure."""
        raise NotImplementedError

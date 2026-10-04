"""B.O.S. Webhook Event Provider v1.0

`event_delivery` provider that publishes business events to webhook subscribers.
"""

from typing import Any, Dict

from integrations.webhooks import WebhookDispatcher

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata

EVENT_DELIVERY = "event_delivery"


class WebhookEventProvider(BaseProvider):
    def __init__(self, priority: int = 10):
        super().__init__(
            ProviderMetadata(
                name="webhook_events",
                capability=EVENT_DELIVERY,
                priority=priority,
                description="Signed webhook delivery to subscribed URLs.",
            )
        )

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action != "emit_event":
            return {"success": False, "error": f"Unsupported event action '{action}'."}
        event = str(params.get("event") or "").strip()
        if not event:
            return {"success": False, "error": "event name is required."}
        data = params.get("data") if isinstance(params.get("data"), dict) else {"value": params.get("data")}
        queued = WebhookDispatcher.publish(f"custom.{event}" if "." not in event else event, data)
        return {"success": True, "event": event, "subscribers": queued}

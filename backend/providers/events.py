"""B.O.S. Provider Lifecycle Events v0.1

Emits provider lifecycle events on the RuntimeEventBus.
"""

from typing import Any, Dict
from runtime.events import RuntimeEventBus, RuntimeEvent, EventType


class ProviderEventType(str):
    PROVIDER_REGISTERED = "ProviderRegistered"
    PROVIDER_LOADED = "ProviderLoaded"
    PROVIDER_ENABLED = "ProviderEnabled"
    PROVIDER_DISABLED = "ProviderDisabled"
    PROVIDER_HEALTH_CHANGED = "ProviderHealthChanged"
    PROVIDER_REMOVED = "ProviderRemoved"


class ProviderEventPublisher:
    """Publishes provider lifecycle state events to RuntimeEventBus."""

    @classmethod
    def publish(cls, event_name: str, provider_name: str, payload: Dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(
            event_type=EventType.SYSTEM,
            source=f"provider:{provider_name}",
            payload={"event_name": event_name, "provider_name": provider_name, **(payload or {})},
        )
        RuntimeEventBus.publish(event)

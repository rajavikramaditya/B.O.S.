"""B.O.S. Service Events v0.1

Emits service lifecycle events (`ServiceRegistered`, `ServiceResolved`, `ServiceStarted`,
`ServiceStopped`, `ServiceReplaced`) on the RuntimeEventBus.
"""

from typing import Any, Dict
from runtime.events import RuntimeEventBus, RuntimeEvent, EventType


class ServiceEventType(str):
    SERVICE_REGISTERED = "ServiceRegistered"
    SERVICE_RESOLVED = "ServiceResolved"
    SERVICE_STARTED = "ServiceStarted"
    SERVICE_STOPPED = "ServiceStopped"
    SERVICE_REPLACED = "ServiceReplaced"


class ServiceEventPublisher:
    """Publishes service lifecycle events to RuntimeEventBus."""

    @classmethod
    def publish(cls, event_name: str, service_name: str, payload: Dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(
            event_type=EventType.SYSTEM,
            source=f"service:{service_name}",
            payload={"event_name": event_name, "service_name": service_name, **(payload or {})},
        )
        RuntimeEventBus.publish(event)

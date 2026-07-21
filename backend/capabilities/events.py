"""B.O.S. Capability Lifecycle Events v0.1

Publishes capability lifecycle events on the RuntimeEventBus.
"""

from typing import Any, Dict


class CapabilityEventType:
    """Capability lifecycle event type constants."""

    CAPABILITY_REGISTERED = "CapabilityRegistered"
    CAPABILITY_ENABLED = "CapabilityEnabled"
    CAPABILITY_DISABLED = "CapabilityDisabled"
    CAPABILITY_RESOLVED = "CapabilityResolved"
    CAPABILITY_FAILED = "CapabilityFailed"


class CapabilityEventPublisher:
    """Publishes capability lifecycle events to RuntimeEventBus."""

    @classmethod
    def publish(
        cls,
        event_name: str,
        capability_name: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        """Publish a capability lifecycle event.

        Delegates to RuntimeEventBus if available.
        Gracefully degrades if EventBus is not initialized.
        """
        try:
            from runtime.events import RuntimeEventBus, RuntimeEvent, EventType

            event = RuntimeEvent(
                event_type=EventType.SYSTEM,
                source=f"capability:{capability_name}",
                payload={
                    "event_name": event_name,
                    "capability_name": capability_name,
                    **(payload or {}),
                },
            )
            RuntimeEventBus.publish(event)
        except Exception:
            # EventBus unavailable during tests or bootstrap — silent degradation
            pass

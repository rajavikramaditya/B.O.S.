"""B.O.S. Module Events v0.1

Emits lifecycle events to RuntimeEventBus for module lifecycle transitions.
"""

from typing import Any, Dict
from runtime.events import RuntimeEventBus, RuntimeEvent, EventType


class ModuleEventType(str):
    MODULE_INSTALLED = "ModuleInstalled"
    MODULE_LOADED = "ModuleLoaded"
    MODULE_ENABLED = "ModuleEnabled"
    MODULE_DISABLED = "ModuleDisabled"
    MODULE_UPDATED = "ModuleUpdated"
    MODULE_REMOVED = "ModuleRemoved"


class ModuleEventPublisher:
    """Publishes module lifecycle events on the RuntimeEventBus."""

    @classmethod
    def publish(cls, event_name: str, module_name: str, payload: Dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(
            event_type=EventType.SYSTEM,
            source=f"module:{module_name}",
            payload={"event_name": event_name, "module_name": module_name, **(payload or {})},
        )
        RuntimeEventBus.publish(event)

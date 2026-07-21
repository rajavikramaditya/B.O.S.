"""B.O.S. Execution Events v0.1

Emits execution lifecycle events (`ExecutionStarted`, `ExecutionCompleted`,
`ExecutionFailed`, `ExecutionCancelled`) on the RuntimeEventBus.
"""

from typing import Any, Dict
from runtime.events import RuntimeEventBus, RuntimeEvent, EventType


class ExecutionEventType(str):
    EXECUTION_STARTED = "ExecutionStarted"
    EXECUTION_COMPLETED = "ExecutionCompleted"
    EXECUTION_FAILED = "ExecutionFailed"
    EXECUTION_CANCELLED = "ExecutionCancelled"


class ExecutionEventPublisher:
    """Publishes command execution events to RuntimeEventBus."""

    @classmethod
    def publish(cls, event_name: str, command_name: str, payload: Dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(
            event_type=EventType.SYSTEM,
            source=f"execution:{command_name}",
            payload={"event_name": event_name, "command_name": command_name, **(payload or {})},
        )
        RuntimeEventBus.publish(event)

"""B.O.S. Runtime Event Data Model v0.1

Event container representing internal and external runtime events.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict
from .event_types import EventType


@dataclass
class RuntimeEvent:
    """Event object published to the B.O.S. Runtime Event Bus."""
    event_type: EventType | str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)
    source: str = "runtime"
    actor_role: str = "customer"

    def get_event_type_str(self) -> str:
        if hasattr(self.event_type, "value"):
            return str(self.event_type.value)
        return str(self.event_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.get_event_type_str(),
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
            "actor_role": self.actor_role,
        }

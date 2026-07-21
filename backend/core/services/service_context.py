"""B.O.S. Service Context v0.1

Execution context injected into services upon resolution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ServiceContext:
    """Runtime context for resolved services."""
    service_id: str
    event_bus: Any = None
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "has_event_bus": self.event_bus is not None,
            "config": self.config,
        }

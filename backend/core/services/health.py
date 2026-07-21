"""B.O.S. Service Health & Diagnostics v0.1

Provides HealthState enum and diagnostic reporting for platform services.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class ServiceHealth:
    """Diagnostic report container for service readiness and liveness."""
    service_name: str
    state: HealthState = HealthState.HEALTHY
    liveness: bool = True
    readiness: bool = True
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "liveness": self.liveness,
            "readiness": self.readiness,
            "details": self.details,
        }

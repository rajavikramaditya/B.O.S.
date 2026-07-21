"""B.O.S. Provider Health & Diagnostics v0.1

Provides health diagnostic checks and health status reporting for registered providers.
"""

from enum import Enum
from typing import Any, Dict, Optional
from .base.base_provider import BaseProvider
from .base.provider_state import ProviderState


class ProviderHealthStatus(str, Enum):
    READY = "READY"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderHealth:
    """Evaluates provider liveness, readiness, and diagnostics status."""

    @classmethod
    def check_health(cls, provider: BaseProvider) -> Dict[str, Any]:
        if provider.state == ProviderState.READY:
            status = ProviderHealthStatus.READY
            live = True
        elif provider.state == ProviderState.DEGRADED:
            status = ProviderHealthStatus.DEGRADED
            live = True
        elif provider.state == ProviderState.STOPPED or provider.state == ProviderState.FAILED:
            status = ProviderHealthStatus.UNAVAILABLE
            live = False
        else:
            status = ProviderHealthStatus.LIVE
            live = True

        return {
            "provider_name": provider.metadata.name,
            "status": status.value,
            "is_live": live,
            "state": provider.state.value if hasattr(provider.state, "value") else provider.state,
            "capability": provider.metadata.capability,
            "priority": provider.metadata.priority,
        }

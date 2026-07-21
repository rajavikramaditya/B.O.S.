"""B.O.S. Provider Resolver v0.1

Selects the optimal active provider for a capability based on priority, health, and availability.
"""

from typing import Any, Dict, Optional
from .base.base_provider import BaseProvider
from .base.provider_state import ProviderState
from .registry import RuntimeProviderRegistry
from .health import ProviderHealth, ProviderHealthStatus


class ProviderResolver:
    """Dynamic provider selection engine."""

    @classmethod
    def resolve(cls, capability: str) -> Optional[BaseProvider]:
        candidates = RuntimeProviderRegistry.get_providers_for_capability(capability)
        if not candidates:
            return None

        # Pick highest priority candidate (lowest priority number) that is in READY state
        for provider in candidates:
            health = ProviderHealth.check_health(provider)
            if health["is_live"] and provider.state == ProviderState.READY:
                return provider

        # Fallback to any live provider if none is READY
        for provider in candidates:
            health = ProviderHealth.check_health(provider)
            if health["is_live"]:
                return provider

        return None

    @classmethod
    def execute_capability(cls, capability: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = cls.resolve(capability)
        if not provider:
            return {
                "success": False,
                "error": f"No available provider resolved for capability '{capability}'.",
            }

        try:
            res = provider.execute(action, params)
            res["resolved_provider"] = provider.metadata.name
            return res
        except Exception as ex:
            return {
                "success": False,
                "error": f"Provider '{provider.metadata.name}' execution failed: {str(ex)}",
            }

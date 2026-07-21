"""B.O.S. Runtime Provider Registry v0.1

Manages runtime provider registration, lookup, enabling/disabling, priority resolution,
and replacement without modifying Core Runtime.
"""

from typing import Any, Dict, List, Optional
from .base.base_provider import BaseProvider
from .base.provider_state import ProviderState
from .events import ProviderEventPublisher, ProviderEventType


class RuntimeProviderRegistry:
    """Registry managing technology providers keyed by name and capability."""

    _providers: Dict[str, BaseProvider] = {}
    _enabled_providers: Dict[str, bool] = {}

    @classmethod
    def register(cls, provider: BaseProvider) -> None:
        name = provider.metadata.name.lower()
        cls._providers[name] = provider
        cls._enabled_providers[name] = True
        provider.state = ProviderState.REGISTERED
        ProviderEventPublisher.publish(
            ProviderEventType.PROVIDER_REGISTERED,
            provider.metadata.name,
            provider.metadata.to_dict(),
        )

    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseProvider]:
        name_lower = name.lower()
        if cls._enabled_providers.get(name_lower, False):
            return cls._providers.get(name_lower)
        return None

    @classmethod
    def get_providers_for_capability(cls, capability: str) -> List[BaseProvider]:
        cap_lower = capability.lower()
        active = []
        for name, provider in cls._providers.items():
            if cls._enabled_providers.get(name, False) and provider.metadata.capability.lower() == cap_lower:
                active.append(provider)
        # Sort by priority ascending (lower number = higher priority, e.g. 10 > 20)
        active.sort(key=lambda p: p.metadata.priority)
        return active

    @classmethod
    def enable_provider(cls, name: str) -> bool:
        name_lower = name.lower()
        if name_lower in cls._providers:
            cls._enabled_providers[name_lower] = True
            ProviderEventPublisher.publish(ProviderEventType.PROVIDER_ENABLED, name)
            return True
        return False

    @classmethod
    def disable_provider(cls, name: str) -> bool:
        name_lower = name.lower()
        if name_lower in cls._providers:
            cls._enabled_providers[name_lower] = False
            ProviderEventPublisher.publish(ProviderEventType.PROVIDER_DISABLED, name)
            return True
        return False

    @classmethod
    def replace_provider(cls, target_name: str, new_provider: BaseProvider) -> None:
        cls.disable_provider(target_name)
        cls.register(new_provider)

    @classmethod
    def unregister(cls, name: str) -> Optional[BaseProvider]:
        name_lower = name.lower()
        cls._enabled_providers.pop(name_lower, None)
        provider = cls._providers.pop(name_lower, None)
        if provider:
            provider.state = ProviderState.UNREGISTERED
            ProviderEventPublisher.publish(ProviderEventType.PROVIDER_REMOVED, name)
        return provider

    @classmethod
    def clear(cls) -> None:
        cls._providers.clear()
        cls._enabled_providers.clear()

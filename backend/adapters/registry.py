"""B.O.S. Adapter Registry v0.1

Central registry for managing external system adapters.
"""

from typing import Any, Dict, List, Optional
from .base_adapter import BaseAdapter


class AdapterRegistry:
    """Registry storing and resolving platform adapters by name or channel type."""

    _adapters: Dict[str, BaseAdapter] = {}

    @classmethod
    def register(cls, adapter: BaseAdapter) -> None:
        cls._adapters[adapter.name.lower()] = adapter

    @classmethod
    def get(cls, name: str) -> Optional[BaseAdapter]:
        return cls._adapters.get(name.lower())

    @classmethod
    def get_by_channel(cls, channel_type: str) -> List[BaseAdapter]:
        chan_lower = channel_type.lower()
        return [
            ad for ad in cls._adapters.values()
            if ad.channel_type.lower() == chan_lower
        ]

    @classmethod
    def list_adapters(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": ad.name,
                "channel_type": ad.channel_type,
                "status": str(ad.status.value if hasattr(ad.status, "value") else ad.status),
            }
            for ad in cls._adapters.values()
        ]

    @classmethod
    def clear(cls) -> None:
        cls._adapters.clear()

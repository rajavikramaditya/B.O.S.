"""B.O.S. External Adapters Package v0.1

Provides BaseAdapter, AdapterRequest, AdapterResponse, AdapterStatus, AdapterRegistry, and AdapterRouter.
"""

from .adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus
from .base_adapter import BaseAdapter
from .registry import AdapterRegistry
from .router import AdapterRouter

__all__ = [
    "AdapterRequest",
    "AdapterResponse",
    "AdapterStatus",
    "BaseAdapter",
    "AdapterRegistry",
    "AdapterRouter",
]

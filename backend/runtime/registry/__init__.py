"""B.O.S. Runtime Capability Registry Package v0.1

Universal capability registry storing metadata, actions, policies, and supported adapters.
"""

from .metadata import CapabilityMetadata
from .base_capability import UniversalCapability
from .registry import UniversalCapabilityRegistry

__all__ = [
    "CapabilityMetadata",
    "UniversalCapability",
    "UniversalCapabilityRegistry",
]

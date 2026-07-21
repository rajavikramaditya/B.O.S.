"""B.O.S. Capability Base Package v0.1

Exports all base capability contracts.
"""

from .base_capability import BaseCapability
from .capability_context import CapabilityContext
from .capability_lifecycle import CapabilityLifecycle
from .capability_metadata import CapabilityMetadata
from .capability_result import CapabilityResult
from .capability_scope import CapabilityScope
from .manifest import CapabilityManifest

# Re-exported for backward compatibility with Frozen Core (backend/runtime/capability.py)
from capabilities.legacy_base import CapabilityRegistry

__all__ = [
    "BaseCapability",
    "CapabilityContext",
    "CapabilityLifecycle",
    "CapabilityMetadata",
    "CapabilityResult",
    "CapabilityScope",
    "CapabilityManifest",
    "CapabilityRegistry",
]


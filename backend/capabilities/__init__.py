"""B.O.S. Capabilities Package v0.1

Provides generic platform capabilities and framework entry points.

Sprint-12 Framework:
  - capabilities.base.*          → New formal contracts (BaseCapability, CapabilityMetadata, etc.)
  - capabilities.registry        → RuntimeCapabilityRegistry
  - capabilities.resolver        → CapabilityResolver
  - capabilities.policies        → CapabilityPolicyManager
  - capabilities.events          → CapabilityEventPublisher
  - capabilities.reference.*     → Reference implementations

Legacy Layer (preserved until domain module extraction in Sprint-13/14):
  - LegacyBaseCapability, LegacyCapabilityResult, LegacyCapabilityRegistry
  - MessagingCapability, SchedulingCapability, MemoryCapability, AutomationCapability
"""

from .legacy_base import (
    BaseCapability as LegacyBaseCapability,
    CapabilityRegistry as LegacyCapabilityRegistry,
    CapabilityResult as LegacyCapabilityResult,
)
from .messaging import MessagingCapability
from .scheduling import SchedulingCapability
from .memory import MemoryCapability
from .automation import AutomationCapability

__all__ = [
    # Legacy (preserved for backward compatibility)
    "LegacyBaseCapability",
    "LegacyCapabilityResult",
    "LegacyCapabilityRegistry",
    "MessagingCapability",
    "SchedulingCapability",
    "MemoryCapability",
    "AutomationCapability",
]


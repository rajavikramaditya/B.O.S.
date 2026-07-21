"""B.O.S. Capabilities Package v0.1

Provides generic platform capabilities and framework entry points.

Sprint-12 Framework:
  - capabilities.base.*          → New formal contracts (BaseCapability, CapabilityMetadata, etc.)
  - capabilities.registry        → RuntimeCapabilityRegistry
  - capabilities.resolver        → CapabilityResolver
  - capabilities.policies        → CapabilityPolicyManager
  - capabilities.events          → CapabilityEventPublisher
  - capabilities.reference.*     → Reference implementations

Legacy Layer (compatibility bridge for Frozen Core v1.0):
  - LegacyCapabilityRegistry     → Compatibility registry wrapping RuntimeCapabilityRegistry
"""

from .legacy_base import (
    CapabilityRegistry as LegacyCapabilityRegistry,
)

__all__ = [
    # Legacy (preserved for backward compatibility with Frozen Core)
    "LegacyCapabilityRegistry",
]



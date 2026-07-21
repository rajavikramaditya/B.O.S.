"""B.O.S. Capabilities Package v0.1

Provides generic platform capabilities (legacy layer — preserved for backward compatibility).

Sprint-12 Framework:
  - capabilities.base.*          → New formal contracts (BaseCapability, CapabilityMetadata, etc.)
  - capabilities.registry        → RuntimeCapabilityRegistry
  - capabilities.resolver        → CapabilityResolver
  - capabilities.policies        → CapabilityPolicyManager
  - capabilities.events          → CapabilityEventPublisher
  - capabilities.reference.*     → Reference implementations

Legacy (KEEP until Radio Module migration in Sprint-13):
  - LegacyCapabilityRegistry     → Old flat registry (still used by runtime/capability.py)
  - MessagingCapability          → Radio-specific messaging (pending migration)
  - SchedulingCapability         → Radio-specific scheduling (pending migration)
  - MemoryCapability             → Neena AI manager memory (pending migration)
  - AutomationCapability         → Radio automation operations (pending migration)
"""

# Legacy layer — imported from the flat module files (NOT from base/ sub-package)
# This preserves backward compatibility with runtime/capability.py and existing tests
import importlib as _importlib
import sys as _sys

# Load legacy base.py explicitly by file path to avoid conflict with base/ package
import types as _types

def _load_legacy_base():
    """Load the legacy base.py module without conflicting with base/ package."""
    import pathlib
    _base_path = pathlib.Path(__file__).parent / "base.py"
    spec = _importlib.util.spec_from_file_location("capabilities._legacy_base", _base_path)
    mod = _importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_legacy_base = _load_legacy_base()

# Legacy exports
LegacyBaseCapability = _legacy_base.BaseCapability
LegacyCapabilityResult = _legacy_base.CapabilityResult
LegacyCapabilityRegistry = _legacy_base.CapabilityRegistry

# Individual capability classes (still use legacy base)
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

"""B.O.S. Capability Lifecycle v0.1

Defines the lifecycle states of a platform capability.
"""

from enum import Enum


class CapabilityLifecycle(str, Enum):
    """Runtime lifecycle state of a registered capability."""

    UNREGISTERED = "UNREGISTERED"   # Not yet registered in RuntimeCapabilityRegistry
    REGISTERED = "REGISTERED"       # Registered but not yet enabled
    ENABLED = "ENABLED"             # Active and available for resolution
    DISABLED = "DISABLED"           # Temporarily inactive (policy or manual)
    DEPRECATED = "DEPRECATED"       # Scheduled for removal — still functional but discouraged

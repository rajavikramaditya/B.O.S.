"""B.O.S. Capability Scope v0.1

Defines the scope of a registered platform capability.
"""

from enum import Enum


class CapabilityScope(str, Enum):
    """Scope of a platform capability."""

    GLOBAL = "GLOBAL"       # Available platform-wide, all modules and tenants
    MODULE = "MODULE"       # Registered by and scoped to a specific Business Module
    TENANT = "TENANT"       # Available only within a specific tenant boundary
    SYSTEM = "SYSTEM"       # Reserved for Core runtime internal capabilities

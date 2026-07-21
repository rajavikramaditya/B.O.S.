"""B.O.S. Provider Lifecycle Enum v0.1

Enumeration of provider lifecycle events and phases.
"""

from enum import Enum


class ProviderLifecycle(str, Enum):
    UNLOADED = "UNLOADED"
    LOADED = "LOADED"
    INITIALIZED = "INITIALIZED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    TERMINATED = "TERMINATED"

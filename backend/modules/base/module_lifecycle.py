"""B.O.S. Module Lifecycle Contract v0.1

Enum and interface defining module lifecycle states.
"""

from enum import Enum


class ModuleLifecycle(str, Enum):
    UNLOADED = "UNLOADED"
    REGISTERED = "REGISTERED"
    LOADED = "LOADED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"

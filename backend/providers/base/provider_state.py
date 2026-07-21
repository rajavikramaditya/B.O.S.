"""B.O.S. Provider State Enum v0.1

Enumeration of provider lifecycle states.
"""

from enum import Enum


class ProviderState(str, Enum):
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

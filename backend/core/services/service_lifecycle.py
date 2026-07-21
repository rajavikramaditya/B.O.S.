"""B.O.S. Service Lifecycle Enum v0.1

Enumeration of service operational states.
"""

from enum import Enum


class ServiceLifecycle(str, Enum):
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

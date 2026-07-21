"""B.O.S. Service Scope Enum v0.1

Enumeration of service resolution scopes.
"""

from enum import Enum


class ServiceScope(str, Enum):
    SINGLETON = "SINGLETON"
    TRANSIENT = "TRANSIENT"
    SCOPED = "SCOPED"

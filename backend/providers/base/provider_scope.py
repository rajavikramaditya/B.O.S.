"""B.O.S. Provider Scope Enum v0.1

Enumeration of provider instantiation scopes.
"""

from enum import Enum


class ProviderScope(str, Enum):
    SINGLETON = "SINGLETON"
    TRANSIENT = "TRANSIENT"
    SCOPED = "SCOPED"

"""B.O.S. Business Relationship Types v0.1

Enumeration of supported entity relationship types.
"""

from enum import Enum


class RelationshipType(str, Enum):
    CONTAINS = "CONTAINS"
    OWNS = "OWNS"
    EMPLOYED_BY = "EMPLOYED_BY"
    SERVES = "SERVES"
    PLACED = "PLACED"
    GENERATED = "GENERATED"
    PAID = "PAID"
    OPENED = "OPENED"
    RESOLVED = "RESOLVED"
    RELATED_TO = "RELATED_TO"

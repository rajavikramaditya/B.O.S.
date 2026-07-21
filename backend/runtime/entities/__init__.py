"""B.O.S. Universal Entities Package v0.1

Provides UniversalEntity model and EntityType enumeration.
"""

from .entity_types import EntityType
from .base_entity import UniversalEntity

__all__ = [
    "EntityType",
    "UniversalEntity",
]

"""B.O.S. Universal Entity Base Model v0.1

Base object model from which all BOS entity objects inherit.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List
from .entity_types import EntityType


@dataclass
class UniversalEntity:
    """Universal base entity model for all B.O.S. platform objects."""
    entity_type: EntityType | str
    name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    owner: str = "system"
    permissions: List[str] = field(default_factory=lambda: ["read", "write"])
    status: str = "ACTIVE"
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    business_id: str = "default_org"
    entity_id: str = field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:12]}")

    def add_relationship(self, target_id: str, relationship: str) -> None:
        self.relationships.append({"target_id": target_id, "relationship": relationship})
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": str(self.entity_type.value if hasattr(self.entity_type, "value") else self.entity_type),
            "name": self.name,
            "metadata": self.metadata,
            "relationships": self.relationships,
            "owner": self.owner,
            "permissions": self.permissions,
            "status": self.status,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "business_id": self.business_id,
        }

"""B.O.S. Graph Query Specification v0.1

Container specifying domain target, entity types, filters, and relationship paths.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .filters import QueryFilter


@dataclass
class GraphQuery:
    """Universal graph query object."""
    target_domain: str  # "business", "knowledge", "workflow", "memory"
    entity_type: str = "*"
    filters: List[QueryFilter] = field(default_factory=list)
    start_node_id: Optional[str] = None
    relationship_path: List[str] = field(default_factory=list)
    limit: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_domain": self.target_domain,
            "entity_type": self.entity_type,
            "filters": [f.__dict__ for f in self.filters],
            "start_node_id": self.start_node_id,
            "relationship_path": self.relationship_path,
            "limit": self.limit,
        }

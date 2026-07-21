"""B.O.S. Business Graph Edge v0.1

Container representing a directed edge linking business nodes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from .relationship import RelationshipType


@dataclass
class BusinessEdge:
    """Edge defining a relationship between two business nodes."""
    source_id: str
    target_id: str
    rel_type: RelationshipType | str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": str(self.rel_type.value if hasattr(self.rel_type, "value") else self.rel_type),
            "metadata": self.metadata,
        }

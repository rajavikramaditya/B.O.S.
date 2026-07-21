"""B.O.S. Knowledge Graph Edge v0.1

Edge representing semantic relationships between knowledge nodes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class KnowledgeEdge:
    """Directed edge linking related knowledge concepts."""
    source_id: str
    target_id: str
    relationship: str  # "SUPERSEDES", "SUPERSEEDED_BY", "DEPENDS_ON", "EXPLAINS", "REFERENCES"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
            "metadata": self.metadata,
        }

"""B.O.S. Capability Graph Edge v0.1

Edge representing relationships between capabilities.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CapabilityEdge:
    """Directed edge linking related capabilities."""
    source_capability: str
    target_capability: str
    relationship_type: str  # "REQUIRES", "TRIGGERS", "ENHANCES", "FALLBACK_TO", "DELEGATES_TO"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_capability": self.source_capability,
            "target_capability": self.target_capability,
            "relationship_type": self.relationship_type,
            "metadata": self.metadata,
        }

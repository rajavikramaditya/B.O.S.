"""B.O.S. Business Graph Node v0.1

Container representing a business entity node.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BusinessNode:
    """Node representing a business entity (e.g., Department, Customer, Order)."""
    node_type: str
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "attributes": self.attributes,
        }

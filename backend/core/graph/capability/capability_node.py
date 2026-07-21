"""B.O.S. Capability Graph Node v0.1

Node representing a capability for graph-based reasoning and discovery.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CapabilityNode:
    """Graph node representing a platform capability."""
    name: str
    description: str = ""
    required_inputs: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_inputs": self.required_inputs,
            "expected_outputs": self.expected_outputs,
            "permissions": self.permissions,
            "metadata": self.metadata,
        }

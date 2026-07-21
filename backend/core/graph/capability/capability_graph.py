"""B.O.S. Capability Graph v0.1

Graph structure representing relationships between platform capabilities.
Used by Planner and Decision Engine for discovery and reasoning.
"""

from typing import Any, Dict, List, Optional
from .capability_node import CapabilityNode
from .capability_edge import CapabilityEdge


class CapabilityGraph:
    """Graph of platform capabilities and inter-capability dependencies."""

    def __init__(self, graph_id: str = "capability_relationships"):
        self.graph_id = graph_id
        self.nodes: Dict[str, CapabilityNode] = {}
        self.edges: List[CapabilityEdge] = []
        self._initialize_default_graph()

    def add_capability(self, node: CapabilityNode) -> None:
        self.nodes[node.name.lower()] = node

    def add_relationship(
        self, source: str, target: str, rel_type: str, metadata: Dict[str, Any] | None = None
    ) -> None:
        edge = CapabilityEdge(
            source_capability=source.lower(),
            target_capability=target.lower(),
            relationship_type=rel_type,
            metadata=metadata or {},
        )
        self.edges.append(edge)

    def get_capability(self, name: str) -> Optional[CapabilityNode]:
        return self.nodes.get(name.lower())

    def _initialize_default_graph(self) -> None:
        """Seed default capability relationships: Messaging -> Notification -> Approval -> Workflow -> Knowledge -> Memory."""
        caps = [
            CapabilityNode("messaging", "Messaging capability"),
            CapabilityNode("notification", "Notification capability"),
            CapabilityNode("approval", "Human approval capability"),
            CapabilityNode("workflow", "Workflow execution capability"),
            CapabilityNode("knowledge", "Knowledge retrieval capability"),
            CapabilityNode("memory", "Memory storage capability"),
            CapabilityNode("scheduling", "Event scheduling capability"),
            CapabilityNode("analytics", "Analytics tracking capability"),
            CapabilityNode("search", "Search capability"),
            CapabilityNode("automation", "Automation trigger capability"),
            CapabilityNode("identity", "Identity verification capability"),
        ]
        for c in caps:
            self.add_capability(c)

        # Standard relationships
        self.add_relationship("messaging", "notification", "ENHANCES")
        self.add_relationship("notification", "approval", "TRIGGERS")
        self.add_relationship("approval", "workflow", "REQUIRES")
        self.add_relationship("workflow", "knowledge", "REQUIRES")
        self.add_relationship("workflow", "memory", "REQUIRES")
        self.add_relationship("scheduling", "notification", "TRIGGERS")
        self.add_relationship("automation", "workflow", "TRIGGERS")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

"""B.O.S. Business Graph Base v0.1

In-memory directed graph representing connected business entity nodes and edges.
"""

from typing import Any, Dict, List, Optional
from .node import BusinessNode
from .edge import BusinessEdge


class BusinessGraph:
    """Base graph structure storing nodes and directed edges."""

    def __init__(self, graph_id: str = "business_context"):
        self.graph_id = graph_id
        self.nodes: Dict[str, BusinessNode] = {}
        self.edges: List[BusinessEdge] = []

    def add_node(self, node: BusinessNode) -> str:
        self.nodes[node.node_id] = node
        return node.node_id

    def get_node(self, node_id: str) -> Optional[BusinessNode]:
        return self.nodes.get(node_id)

    def add_edge(self, source_id: str, target_id: str, rel_type: str, metadata: Dict[str, Any] | None = None) -> None:
        edge = BusinessEdge(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            metadata=metadata or {},
        )
        self.edges.append(edge)

    def get_connected_nodes(self, node_id: str, direction: str = "outgoing") -> List[BusinessNode]:
        connected_ids = []
        for edge in self.edges:
            if direction in ("outgoing", "both") and edge.source_id == node_id:
                connected_ids.append(edge.target_id)
            if direction in ("incoming", "both") and edge.target_id == node_id:
                connected_ids.append(edge.source_id)

        return [self.nodes[nid] for nid in connected_ids if nid in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

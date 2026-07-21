"""B.O.S. Knowledge Graph Base v0.1

Graph structure storing knowledge nodes and relationships.
"""

from typing import Any, Dict, List, Optional
from .knowledge_node import KnowledgeNode
from .knowledge_edge import KnowledgeEdge


class KnowledgeGraph:
    """Stores knowledge nodes and their semantic links."""

    def __init__(self, graph_id: str = "knowledge_base"):
        self.graph_id = graph_id
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []

    def add_node(self, node: KnowledgeNode) -> str:
        self.nodes[node.node_id] = node
        return node.node_id

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def add_edge(self, source_id: str, target_id: str, relationship: str, metadata: Dict[str, Any] | None = None) -> None:
        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            metadata=metadata or {},
        )
        self.edges.append(edge)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

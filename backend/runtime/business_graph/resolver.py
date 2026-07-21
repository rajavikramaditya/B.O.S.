"""B.O.S. Relationship Resolver v0.1

Traverses relationships and resolves connected entities.
"""

from typing import Any, Dict, List
from .graph import BusinessGraph
from .node import BusinessNode


class RelationshipResolver:
    """Traverses graph paths to resolve related entities."""

    @classmethod
    def resolve_path(cls, graph: BusinessGraph, start_node_id: str, target_type: str) -> List[BusinessNode]:
        results: List[BusinessNode] = []
        visited = set()
        queue = [start_node_id]

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)

            curr_node = graph.get_node(curr_id)
            if curr_node and curr_node.node_type.lower() == target_type.lower():
                results.append(curr_node)

            for neighbor in graph.get_connected_nodes(curr_id, direction="both"):
                if neighbor.node_id not in visited:
                    queue.append(neighbor.node_id)

        return results

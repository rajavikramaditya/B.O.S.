"""B.O.S. Capability Resolver v0.1

Discovers capability relationships, dependent capabilities, and fallback paths.
"""

from typing import Any, Dict, List
from .capability_graph import CapabilityGraph
from .capability_node import CapabilityNode


class CapabilityResolver:
    """Resolves capability relationships for Planner and Decision Engine reasoning."""

    @classmethod
    def find_related_capabilities(
        cls, graph: CapabilityGraph, capability_name: str, relationship_type: str | None = None
    ) -> List[CapabilityNode]:
        name_clean = capability_name.lower()
        results: List[CapabilityNode] = []

        for edge in graph.edges:
            if edge.source_capability == name_clean:
                if relationship_type is None or edge.relationship_type.upper() == relationship_type.upper():
                    target_node = graph.get_capability(edge.target_capability)
                    if target_node:
                        results.append(target_node)

        return results

    @classmethod
    def find_prerequisites(cls, graph: CapabilityGraph, capability_name: str) -> List[CapabilityNode]:
        """Find capabilities that require or trigger the specified capability."""
        name_clean = capability_name.lower()
        results: List[CapabilityNode] = []

        for edge in graph.edges:
            if edge.target_capability == name_clean and edge.relationship_type in ("REQUIRES", "TRIGGERS"):
                src_node = graph.get_capability(edge.source_capability)
                if src_node:
                    results.append(src_node)

        return results

"""B.O.S. Knowledge Index v0.1

Index for searching knowledge nodes by category, tags, or content keywords.
"""

from typing import Any, Dict, List
from .knowledge_graph import KnowledgeGraph
from .knowledge_node import KnowledgeNode


class KnowledgeIndex:
    """Keyword and tag index for knowledge graph retrieval."""

    @classmethod
    def search(cls, graph: KnowledgeGraph, query: str, category: str | None = None) -> List[KnowledgeNode]:
        q_lower = (query or "").lower()
        results = []

        for node in graph.nodes.values():
            if category and node.category.lower() != category.lower():
                continue

            matches_query = (
                q_lower in node.title.lower()
                or q_lower in node.content.lower()
                or any(q_lower in t.lower() for t in node.tags)
            )
            if matches_query or not q_lower:
                results.append(node)

        return results

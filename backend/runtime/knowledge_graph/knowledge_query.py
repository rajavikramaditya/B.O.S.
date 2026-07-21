"""B.O.S. Knowledge Query Engine v0.1

Query interface for searching facts, rules, policies, and references in the Knowledge Graph.
"""

from typing import Any, Dict, List
from .knowledge_graph import KnowledgeGraph
from .knowledge_node import KnowledgeNode
from .knowledge_index import KnowledgeIndex


class KnowledgeQueryEngine:
    """Executes knowledge queries against KnowledgeGraph before execution."""

    @classmethod
    def query_knowledge(
        cls, graph: KnowledgeGraph, query: str, category: str | None = None
    ) -> List[Dict[str, Any]]:
        nodes = KnowledgeIndex.search(graph, query, category)
        return [n.to_dict() for n in nodes]

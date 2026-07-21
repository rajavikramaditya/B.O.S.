"""B.O.S. Graph Resolver v0.1

Dispatches graph queries across Business Graph, Knowledge Graph, Workflow Graph, and Workflow Memory.
"""

from typing import Any, Dict, List
from .query import GraphQuery
from ..business_graph import BusinessContextGraph
from ..knowledge_graph import KnowledgeGraph, KnowledgeIndex
from ..workflow_memory import WorkflowMemory


class GraphResolver:
    """Dispatches and resolves graph queries across distinct runtime graphs."""

    @classmethod
    def resolve(
        cls,
        query: GraphQuery,
        business_graph: BusinessContextGraph | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ) -> List[Dict[str, Any]]:
        domain = query.target_domain.lower()
        results: List[Dict[str, Any]] = []

        if domain == "business" and business_graph:
            if query.start_node_id:
                nodes = business_graph.find_related_entities(query.start_node_id, query.entity_type)
            else:
                nodes = list(business_graph.nodes.values())

            for n in nodes:
                n_dict = n.to_dict()
                if query.entity_type not in ("*", n.node_type):
                    continue
                if all(f.matches(n_dict.get("attributes", {})) or f.matches(n_dict) for f in query.filters):
                    results.append(n_dict)

        elif domain == "knowledge" and knowledge_graph:
            kw = query.filters[0].value if query.filters else ""
            nodes = KnowledgeIndex.search(
                knowledge_graph,
                query=str(kw) if kw else "",
                category=query.entity_type if query.entity_type != "*" else None,
            )
            results = [n.to_dict() for n in nodes]

        elif domain == "memory":
            hist = WorkflowMemory.get_history(limit=query.limit)
            results = [hist]

        return results[: query.limit]

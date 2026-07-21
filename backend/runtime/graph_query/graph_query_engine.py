"""B.O.S. Graph Query Engine v0.1

Unified entry point for graph queries across Business Graph, Knowledge Graph,
Workflow Graph, and Workflow Memory.
"""

from typing import Any, Dict, List, Optional
from .query import GraphQuery
from .filters import QueryFilter
from .resolver import GraphResolver
from ..business_graph import BusinessContextGraph
from ..knowledge_graph import KnowledgeGraph


class GraphQueryEngine:
    """Universal query interface for searching entities, relationships, knowledge, and history."""

    @classmethod
    def execute_query(
        cls,
        query: GraphQuery,
        business_graph: BusinessContextGraph | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ) -> List[Dict[str, Any]]:
        return GraphResolver.resolve(query, business_graph, knowledge_graph)

    @classmethod
    def find_entity(
        cls,
        entity_type: str,
        business_graph: BusinessContextGraph,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        query_filters = []
        if filters:
            for k, v in filters.items():
                query_filters.append(QueryFilter(field=k, operator="eq", value=v))

        query = GraphQuery(
            target_domain="business",
            entity_type=entity_type,
            filters=query_filters,
        )
        return cls.execute_query(query, business_graph=business_graph)

    @classmethod
    def find_knowledge(
        cls,
        query_text: str,
        knowledge_graph: KnowledgeGraph,
        category: str | None = None,
    ) -> List[Dict[str, Any]]:
        query = GraphQuery(
            target_domain="knowledge",
            entity_type=category or "*",
            filters=[QueryFilter(field="query", operator="contains", value=query_text)],
        )
        return cls.execute_query(query, knowledge_graph=knowledge_graph)

"""B.O.S. Business Context Graph v0.1

Runtime context graph representing business relationship topology:
Business -> Department -> Employee -> Customer -> Order -> Invoice -> Payment -> Support Ticket -> Resolution
"""

from typing import Any, Dict, List, Optional
from .graph import BusinessGraph
from .node import BusinessNode
from .relationship import RelationshipType
from .resolver import RelationshipResolver


class BusinessContextGraph(BusinessGraph):
    """Runtime representation of connected business entities and relationships."""

    def __init__(self, graph_id: str = "business_context"):
        super().__init__(graph_id=graph_id)

    def find_related_entities(self, start_node_id: str, target_type: str) -> List[BusinessNode]:
        return RelationshipResolver.resolve_path(self, start_node_id, target_type)

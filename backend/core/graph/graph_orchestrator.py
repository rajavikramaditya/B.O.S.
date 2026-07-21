"""B.O.S. Graph Orchestrator v0.1

Central coordinator providing unified graph context access across Business Graph,
Knowledge Graph, Capability Graph, Workflow Graph, and Workflow Memory.
Runtime requests graph context ONLY through GraphOrchestrator while graphs remain independent.
"""

from typing import Any, Dict, List, Optional
from .business import BusinessContextGraph
from .knowledge import KnowledgeGraph, KnowledgeIndex
from .capability import CapabilityGraph, CapabilityResolver
from runtime.workflow_memory import WorkflowMemory
from runtime.context import ExecutionContext


class GraphOrchestrator:
    """Coordinates independent graph instances and queries for Runtime execution."""

    def __init__(
        self,
        business_graph: BusinessContextGraph | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        capability_graph: CapabilityGraph | None = None,
    ):
        self.business_graph = business_graph or BusinessContextGraph()
        self.knowledge_graph = knowledge_graph or KnowledgeGraph()
        self.capability_graph = capability_graph or CapabilityGraph()

    def query_business_relationships(self, start_node_id: str, target_type: str) -> List[Dict[str, Any]]:
        nodes = self.business_graph.find_related_entities(start_node_id, target_type)
        return [n.to_dict() for n in nodes]

    def search_knowledge(self, query: str, category: str | None = None) -> List[Dict[str, Any]]:
        nodes = KnowledgeIndex.search(self.knowledge_graph, query, category)
        return [n.to_dict() for n in nodes]

    def discover_capability_prerequisites(self, capability_name: str) -> List[Dict[str, Any]]:
        nodes = CapabilityResolver.find_prerequisites(self.capability_graph, capability_name)
        return [n.to_dict() for n in nodes]

    def recall_workflow_pattern(self, goal: str) -> Optional[Dict[str, Any]]:
        return WorkflowMemory.recall_pattern_for_goal(goal)

    def assemble_graph_context(self, context: ExecutionContext, goal: str) -> Dict[str, Any]:
        """Assembles unified graph context container for Runtime reasoning engines."""
        pattern = self.recall_workflow_pattern(goal)
        knowledge_hits = self.search_knowledge(goal)
        cap_prereqs = self.discover_capability_prerequisites("workflow")

        return {
            "execution_id": context.execution_id,
            "recalled_pattern": pattern,
            "relevant_knowledge": knowledge_hits,
            "capability_dependencies": cap_prereqs,
        }

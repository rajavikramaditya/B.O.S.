"""B.O.S. Workflow Graph Architecture v0.1

State graph model supporting nodes, edges, conditional branching, approval pauses,
retries, fallbacks, and recovery.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from .state import RuntimeState


class NodeType(str, Enum):
    START = "START"
    OBSERVE = "OBSERVE"
    UNDERSTAND = "UNDERSTAND"
    CONTEXT = "CONTEXT"
    REASON = "REASON"
    PLAN = "PLAN"
    POLICY = "POLICY"
    CAPABILITY_SELECT = "CAPABILITY_SELECT"
    APPROVAL = "APPROVAL"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    RETRY = "RETRY"
    FALLBACK = "FALLBACK"
    MEMORY = "MEMORY"
    RESPONSE = "RESPONSE"
    END = "END"


class ConditionType(str, Enum):
    ALWAYS = "ALWAYS"
    IF_SUCCESS = "IF_SUCCESS"
    IF_FAILURE = "IF_FAILURE"
    IF_APPROVAL_REQUIRED = "IF_APPROVAL_REQUIRED"
    IF_RETRY_AVAILABLE = "IF_RETRY_AVAILABLE"
    IF_MAX_RETRIES_EXCEEDED = "IF_MAX_RETRIES_EXCEEDED"
    CUSTOM = "CUSTOM"


@dataclass
class WorkflowNode:
    node_id: str
    name: str
    node_type: NodeType
    handler: Optional[Callable[[RuntimeState], RuntimeState]] = None
    description: str = ""


@dataclass
class WorkflowEdge:
    source_node: str
    target_node: str
    condition_type: ConditionType = ConditionType.ALWAYS
    condition_fn: Optional[Callable[[RuntimeState], bool]] = None


class WorkflowGraph:
    """Graph structure representing runtime execution workflows."""

    def __init__(self, graph_id: str = "default_bos_graph"):
        self.graph_id = graph_id
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: Dict[str, List[WorkflowEdge]] = {}

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes[node.node_id] = node
        if node.node_id not in self.edges:
            self.edges[node.node_id] = []

    def add_edge(
        self,
        source: str,
        target: str,
        condition_type: ConditionType = ConditionType.ALWAYS,
        condition_fn: Optional[Callable[[RuntimeState], bool]] = None,
    ) -> None:
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not in graph.")
        if target not in self.nodes:
            raise ValueError(f"Target node '{target}' not in graph.")

        edge = WorkflowEdge(
            source_node=source,
            target_node=target,
            condition_type=condition_type,
            condition_fn=condition_fn,
        )
        self.edges[source].append(edge)

    def get_next_node(self, current_node_id: str, state: RuntimeState) -> Optional[str]:
        outgoing_edges = self.edges.get(current_node_id, [])
        for edge in outgoing_edges:
            if self._evaluate_edge_condition(edge, state):
                return edge.target_node
        return None

    def _evaluate_edge_condition(self, edge: WorkflowEdge, state: RuntimeState) -> bool:
        cond = edge.condition_type
        if cond == ConditionType.ALWAYS:
            return True
        elif cond == ConditionType.IF_SUCCESS:
            return state.verification_data.get("verified", True) and not state.errors
        elif cond == ConditionType.IF_FAILURE:
            return bool(state.errors) or not state.verification_data.get("verified", True)
        elif cond == ConditionType.IF_APPROVAL_REQUIRED:
            return bool(state.policy_data.get("requires_confirmation", False))
        elif cond == ConditionType.IF_RETRY_AVAILABLE:
            return state.retry_count < state.max_retries
        elif cond == ConditionType.IF_MAX_RETRIES_EXCEEDED:
            return state.retry_count >= state.max_retries
        elif cond == ConditionType.CUSTOM and edge.condition_fn:
            return edge.condition_fn(state)
        return False

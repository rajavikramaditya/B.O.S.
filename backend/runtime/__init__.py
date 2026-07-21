"""B.O.S. Core Runtime Package v0.1 (Workflow Graph Architecture)

Provides universal workflow graph execution engine and state machine for Business Operating System.
"""

from .engine import BOSRuntimeEngine, process_message
from .state import RuntimeState, WorkflowStatus, ExecutionHistoryEntry, Checkpoint
from .graph import WorkflowGraph, WorkflowNode, WorkflowEdge, NodeType, ConditionType
from .planner import GraphPlanner
from .contracts import (
    NormalizedRequest,
    BusinessIntent,
    RuntimeContext,
    ExecutionPlan,
    PolicyDecision,
    ExecutionResult,
    VerificationReport,
    RuntimeResponse,
)

__all__ = [
    "BOSRuntimeEngine",
    "process_message",
    "RuntimeState",
    "WorkflowStatus",
    "ExecutionHistoryEntry",
    "Checkpoint",
    "WorkflowGraph",
    "WorkflowNode",
    "WorkflowEdge",
    "NodeType",
    "ConditionType",
    "GraphPlanner",
    "NormalizedRequest",
    "BusinessIntent",
    "RuntimeContext",
    "ExecutionPlan",
    "PolicyDecision",
    "ExecutionResult",
    "VerificationReport",
    "RuntimeResponse",
]

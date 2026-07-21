"""B.O.S. Graph Planner v0.1

Produces a executable WorkflowGraph plan from user goals and business intent.
"""

from typing import Dict, Any
from .contracts import NormalizedRequest, BusinessIntent, RuntimeContext
from .graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class GraphPlanner:
    """Generates execution workflow graphs tailored for user intent and context."""

    @classmethod
    def build_workflow_graph(
        cls,
        request: NormalizedRequest,
        intent: BusinessIntent,
        context: RuntimeContext,
    ) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id=f"graph_{intent.intent_type}")

        # Core Graph Nodes
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe & Normalize Input", NodeType.OBSERVE),
            WorkflowNode("UNDERSTAND", "Understand Intent & Goal", NodeType.UNDERSTAND),
            WorkflowNode("CONTEXT", "Load Business Context", NodeType.CONTEXT),
            WorkflowNode("REASON", "Evaluate Execution Strategy", NodeType.REASON),
            WorkflowNode("PLAN", "Formulate Workflow Plan", NodeType.PLAN),
            WorkflowNode("POLICY", "Evaluate Policy & Safety", NodeType.POLICY),
            WorkflowNode("APPROVAL", "Await Human Approval", NodeType.APPROVAL),
            WorkflowNode("CAPABILITY_SELECT", "Select Platform Capabilities", NodeType.CAPABILITY_SELECT),
            WorkflowNode("EXECUTE", "Execute Capability Action", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Execution & Truth", NodeType.VERIFY),
            WorkflowNode("RETRY", "Retry Failed Step", NodeType.RETRY),
            WorkflowNode("MEMORY", "Update Memory State", NodeType.MEMORY),
            WorkflowNode("RESPONSE", "Generate Final Response", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        # Graph Edges with Conditional Branching
        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "UNDERSTAND")
        graph.add_edge("UNDERSTAND", "CONTEXT")
        graph.add_edge("CONTEXT", "REASON")
        graph.add_edge("REASON", "PLAN")
        graph.add_edge("PLAN", "POLICY")

        # Policy Branching: If approval required -> APPROVAL node; else -> CAPABILITY_SELECT
        graph.add_edge("POLICY", "APPROVAL", ConditionType.IF_APPROVAL_REQUIRED)
        graph.add_edge("POLICY", "CAPABILITY_SELECT", ConditionType.ALWAYS)
        graph.add_edge("APPROVAL", "CAPABILITY_SELECT", ConditionType.IF_SUCCESS)
        graph.add_edge("APPROVAL", "RESPONSE", ConditionType.IF_FAILURE)

        graph.add_edge("CAPABILITY_SELECT", "EXECUTE")
        graph.add_edge("EXECUTE", "VERIFY")

        # Verification Branching: If failure & retry available -> RETRY -> EXECUTE; else -> MEMORY
        graph.add_edge("VERIFY", "RETRY", ConditionType.IF_FAILURE)
        graph.add_edge("RETRY", "EXECUTE", ConditionType.IF_RETRY_AVAILABLE)
        graph.add_edge("RETRY", "MEMORY", ConditionType.IF_MAX_RETRIES_EXCEEDED)
        graph.add_edge("VERIFY", "MEMORY", ConditionType.IF_SUCCESS)

        graph.add_edge("MEMORY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

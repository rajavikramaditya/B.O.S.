"""B.O.S. Approval Workflow Template v0.1

Template for Human-in-the-loop owner approval workflows.
"""

from typing import Any, Dict
from .base import BaseWorkflowTemplate
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class ApprovalWorkflowTemplate(BaseWorkflowTemplate):
    """Workflow graph template for protected actions requiring human approval."""

    def __init__(self):
        super().__init__(
            name="approval_workflow",
            description="Human-in-the-loop approval workflow template.",
        )

    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id="approval_workflow_graph")
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe Request", NodeType.OBSERVE),
            WorkflowNode("POLICY", "Evaluate Policy & Confirmation", NodeType.POLICY),
            WorkflowNode("APPROVAL", "Await Human Approval", NodeType.APPROVAL),
            WorkflowNode("EXECUTE", "Execute Approved Action", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Execution", NodeType.VERIFY),
            WorkflowNode("RESPONSE", "Generate Response", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "POLICY")
        graph.add_edge("POLICY", "APPROVAL", ConditionType.IF_APPROVAL_REQUIRED)
        graph.add_edge("POLICY", "EXECUTE", ConditionType.ALWAYS)
        graph.add_edge("APPROVAL", "EXECUTE", ConditionType.IF_SUCCESS)
        graph.add_edge("APPROVAL", "RESPONSE", ConditionType.IF_FAILURE)
        graph.add_edge("EXECUTE", "VERIFY")
        graph.add_edge("VERIFY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

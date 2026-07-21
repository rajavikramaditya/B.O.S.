"""B.O.S. Customer Request Workflow Template v0.1

Template for handling incoming customer inquiries, support requests, and thread recall.
"""

from typing import Any, Dict
from .base import BaseWorkflowTemplate
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class CustomerRequestWorkflowTemplate(BaseWorkflowTemplate):
    """Workflow graph template for external customer request handling."""

    def __init__(self):
        super().__init__(
            name="customer_request_workflow",
            description="Customer inquiry and chat workflow template.",
        )

    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id="customer_request_workflow_graph")
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe Customer Message", NodeType.OBSERVE),
            WorkflowNode("UNDERSTAND", "Detect Customer Intent", NodeType.UNDERSTAND),
            WorkflowNode("EXECUTE", "Generate Customer Reply", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Reply Safety", NodeType.VERIFY),
            WorkflowNode("MEMORY", "Save Customer Memory", NodeType.MEMORY),
            WorkflowNode("RESPONSE", "Deliver Response", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "UNDERSTAND")
        graph.add_edge("UNDERSTAND", "EXECUTE")
        graph.add_edge("EXECUTE", "VERIFY")
        graph.add_edge("VERIFY", "MEMORY")
        graph.add_edge("MEMORY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

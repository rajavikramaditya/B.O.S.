"""B.O.S. Notification Workflow Template v0.1

Template for alert, broadcast, and notification workflows.
"""

from typing import Any, Dict
from .base import BaseWorkflowTemplate
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class NotificationWorkflowTemplate(BaseWorkflowTemplate):
    """Workflow graph template for notification and alert workflows."""

    def __init__(self):
        super().__init__(
            name="notification_workflow",
            description="Notification and alert distribution workflow template.",
        )

    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id="notification_workflow_graph")
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe Event", NodeType.OBSERVE),
            WorkflowNode("CAPABILITY_SELECT", "Select Notification Capability", NodeType.CAPABILITY_SELECT),
            WorkflowNode("EXECUTE", "Send Notification", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Delivery", NodeType.VERIFY),
            WorkflowNode("RESPONSE", "Confirm Notification Sent", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "CAPABILITY_SELECT")
        graph.add_edge("CAPABILITY_SELECT", "EXECUTE")
        graph.add_edge("EXECUTE", "VERIFY")
        graph.add_edge("VERIFY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

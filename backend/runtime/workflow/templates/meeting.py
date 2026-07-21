"""B.O.S. Meeting Workflow Template v0.1

Template for scheduling events, meetings, and calendar appointments.
"""

from typing import Any, Dict
from .base import BaseWorkflowTemplate
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class MeetingWorkflowTemplate(BaseWorkflowTemplate):
    """Workflow graph template for scheduling and calendar workflows."""

    def __init__(self):
        super().__init__(
            name="meeting_workflow",
            description="Meeting scheduling and calendar event workflow template.",
        )

    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id="meeting_workflow_graph")
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe Scheduling Request", NodeType.OBSERVE),
            WorkflowNode("UNDERSTAND", "Extract Participants & Time", NodeType.UNDERSTAND),
            WorkflowNode("CONTEXT", "Load Participant Availability", NodeType.CONTEXT),
            WorkflowNode("CAPABILITY_SELECT", "Select Scheduling Capability", NodeType.CAPABILITY_SELECT),
            WorkflowNode("EXECUTE", "Create Meeting Event", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Meeting Created", NodeType.VERIFY),
            WorkflowNode("RESPONSE", "Generate Meeting Confirmation", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "UNDERSTAND")
        graph.add_edge("UNDERSTAND", "CONTEXT")
        graph.add_edge("CONTEXT", "CAPABILITY_SELECT")
        graph.add_edge("CAPABILITY_SELECT", "EXECUTE")
        graph.add_edge("EXECUTE", "VERIFY")
        graph.add_edge("VERIFY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

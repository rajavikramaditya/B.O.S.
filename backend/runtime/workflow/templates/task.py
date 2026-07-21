"""B.O.S. Task Workflow Template v0.1

Template for task creation, assignment, tracking, and execution workflows.
"""

from typing import Any, Dict
from .base import BaseWorkflowTemplate
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class TaskWorkflowTemplate(BaseWorkflowTemplate):
    """Workflow graph template for task management workflows."""

    def __init__(self):
        super().__init__(
            name="task_workflow",
            description="Task assignment, tracking, and execution workflow template.",
        )

    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        graph = WorkflowGraph(graph_id="task_workflow_graph")
        nodes = [
            WorkflowNode("START", "Start Execution", NodeType.START),
            WorkflowNode("OBSERVE", "Observe Task Request", NodeType.OBSERVE),
            WorkflowNode("UNDERSTAND", "Extract Task Details", NodeType.UNDERSTAND),
            WorkflowNode("PLAN", "Formulate Task Plan", NodeType.PLAN),
            WorkflowNode("CAPABILITY_SELECT", "Select Task Capability", NodeType.CAPABILITY_SELECT),
            WorkflowNode("EXECUTE", "Execute Task Action", NodeType.EXECUTE),
            WorkflowNode("VERIFY", "Verify Task Completion", NodeType.VERIFY),
            WorkflowNode("MEMORY", "Update Task Memory", NodeType.MEMORY),
            WorkflowNode("RESPONSE", "Generate Task Report", NodeType.RESPONSE),
            WorkflowNode("END", "End Execution", NodeType.END),
        ]
        for n in nodes:
            graph.add_node(n)

        graph.add_edge("START", "OBSERVE")
        graph.add_edge("OBSERVE", "UNDERSTAND")
        graph.add_edge("UNDERSTAND", "PLAN")
        graph.add_edge("PLAN", "CAPABILITY_SELECT")
        graph.add_edge("CAPABILITY_SELECT", "EXECUTE")
        graph.add_edge("EXECUTE", "VERIFY")
        graph.add_edge("VERIFY", "MEMORY")
        graph.add_edge("MEMORY", "RESPONSE")
        graph.add_edge("RESPONSE", "END")

        return graph

"""B.O.S. Base Workflow Template v0.1

Abstract Base Class for reusable workflow graph templates.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from ...graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType


class BaseWorkflowTemplate(ABC):
    """Abstract base class for reusable B.O.S. Workflow Graph Templates."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def build_graph(self, params: Dict[str, Any] | None = None) -> WorkflowGraph:
        """Construct and return a configured WorkflowGraph instance."""
        pass

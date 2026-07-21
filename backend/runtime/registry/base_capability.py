"""B.O.S. Universal Capability Base v0.1

Abstract Base Class for universal capabilities exposed to the Runtime.
Capabilities select adapters; Planner selects capabilities.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from .metadata import CapabilityMetadata


class UniversalCapability(ABC):
    """Abstract base class for all universal capabilities in B.O.S."""

    def __init__(self, metadata: CapabilityMetadata):
        self.metadata = metadata

    @property
    def name(self) -> str:
        return self.metadata.name

    @abstractmethod
    def supported_actions(self) -> List[str]:
        """Return list of action primitives supported by this capability."""
        pass

    @abstractmethod
    def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action via selected adapter."""
        pass

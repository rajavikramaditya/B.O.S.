"""B.O.S. Capability Foundation v0.1

Base classes and registry for generic platform capabilities.
Capabilities describe platform actions independently of external providers or adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CapabilityResult:
    """Standard output envelope returned by all capability executions."""
    success: bool
    capability_name: str
    action: str
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: Optional[str] = None


class BaseCapability(ABC):
    """Abstract Base Class for all B.O.S. Capabilities."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def supported_actions(self) -> List[str]:
        """Return list of supported action names."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> CapabilityResult:
        """Execute the capability action with given params."""
        pass


class CapabilityRegistry:
    """Global registry for platform capabilities."""

    _capabilities: Dict[str, BaseCapability] = {}

    @classmethod
    def register(cls, capability: BaseCapability) -> None:
        cls._capabilities[capability.name.lower()] = capability

    @classmethod
    def get(cls, name: str) -> Optional[BaseCapability]:
        return cls._capabilities.get(name.lower())

    @classmethod
    def list_capabilities(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": cap.name,
                "description": cap.description,
                "supported_actions": cap.supported_actions(),
            }
            for cap in cls._capabilities.values()
        ]

    @classmethod
    def resolve_capability_for_action(cls, action: str) -> Optional[BaseCapability]:
        for cap in cls._capabilities.values():
            if action in cap.supported_actions():
                return cap
        return None

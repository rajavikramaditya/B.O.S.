"""B.O.S. Base Provider Abstract Class v0.1

Abstract Base Class for all infrastructure providers in B.O.S.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from .provider_metadata import ProviderMetadata
from .provider_context import ProviderContext
from .provider_state import ProviderState


class BaseProvider(ABC):
    """Abstract base class for platform technology providers."""

    def __init__(self, metadata: ProviderMetadata):
        self.metadata = metadata
        self.state = ProviderState.UNREGISTERED
        self.context: ProviderContext | None = None

    def initialize(self, context: ProviderContext) -> None:
        self.context = context
        self.state = ProviderState.INITIALIZING
        self._on_initialize(context)
        self.state = ProviderState.READY

    def shutdown(self) -> None:
        self._on_shutdown()
        self.state = ProviderState.STOPPED

    @abstractmethod
    def _on_initialize(self, context: ProviderContext) -> None:
        """Subclass setup logic."""
        pass

    @abstractmethod
    def _on_shutdown(self) -> None:
        """Subclass cleanup logic."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute provider capability action and return dictionary result."""
        pass

"""B.O.S. Abstract Base Service v0.1

Abstract Base Class for all system services in B.O.S.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from .service_metadata import ServiceMetadata
from .service_lifecycle import ServiceLifecycle
from .service_context import ServiceContext


class BaseService(ABC):
    """Abstract base class for platform services."""

    def __init__(self, metadata: ServiceMetadata):
        self.metadata = metadata
        self.status = ServiceLifecycle.UNREGISTERED
        self.context: ServiceContext | None = None

    @abstractmethod
    def start(self, context: ServiceContext) -> bool:
        """Initialize service lifecycle."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop service lifecycle."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return health diagnostics."""
        pass

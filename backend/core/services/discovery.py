"""B.O.S. Service Discovery v0.1

Public entry point allowing Modules, Runtime, Graphs, Capabilities, and Adapters
to discover and resolve system services exclusively through the Service Layer.
"""

from typing import Any, Dict, Optional
from .base_service import BaseService
from .container import ServiceContainer
from .registry import RuntimeServiceRegistry


class ServiceDiscovery:
    """Public discovery facade for resolving platform services."""

    @classmethod
    def get_service(cls, service_name: str) -> Optional[BaseService]:
        """Resolve service by name via Dependency Injection Container."""
        try:
            return ServiceContainer.resolve_with_dependencies(service_name)
        except (KeyError, CircularDependencyError):
            return None

    @classmethod
    def is_service_available(cls, service_name: str) -> bool:
        """Check if service is registered and available."""
        return RuntimeServiceRegistry.resolve(service_name) is not None

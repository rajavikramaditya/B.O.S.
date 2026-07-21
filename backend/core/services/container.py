"""B.O.S. Dependency Injection Container v0.1

Provides automatic constructor injection, lazy resolution, dependency graph checking,
and circular dependency detection across services.
"""

from typing import Any, Dict, List, Set, Type
from .base_service import BaseService
from .registry import RuntimeServiceRegistry
from .service_context import ServiceContext
from .service_lifecycle import ServiceLifecycle
from runtime.events import RuntimeEventBus


class CircularDependencyError(Exception):
    """Raised when a circular dependency loop is detected in the ServiceContainer."""
    pass


class ServiceContainer:
    """Dependency Injection container resolving service instances and dependencies."""

    @classmethod
    def resolve_with_dependencies(
        cls, service_name: str, resolving_stack: Set[str] | None = None
    ) -> BaseService:
        resolving = resolving_stack or set()
        name_lower = service_name.lower()

        if name_lower in resolving:
            cycle = " -> ".join(list(resolving) + [name_lower])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")

        svc = RuntimeServiceRegistry.resolve(name_lower)
        if not svc:
            raise KeyError(f"Service '{service_name}' is not registered in RuntimeServiceRegistry.")

        resolving.add(name_lower)

        # Resolve declared dependencies recursively
        for dep in svc.metadata.dependencies:
            cls.resolve_with_dependencies(dep, resolving.copy())

        # Start service if unregistered
        if svc.status != ServiceLifecycle.RUNNING:
            ctx = ServiceContext(service_id=svc.metadata.name, event_bus=RuntimeEventBus)
            svc.start(ctx)

        return svc

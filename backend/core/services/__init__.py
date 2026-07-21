"""B.O.S. Generic Service Layer Package v0.1

Provides BaseService, ServiceMetadata, ServiceContext, ServiceScope, ServiceLifecycle,
RuntimeServiceRegistry, ServiceContainer, CircularDependencyError, ServiceDiscovery,
ServiceHealth, HealthState, and ServiceEventPublisher.
"""

from .service_scope import ServiceScope
from .service_lifecycle import ServiceLifecycle
from .service_metadata import ServiceMetadata
from .service_context import ServiceContext
from .base_service import BaseService
from .registry import RuntimeServiceRegistry
from .container import ServiceContainer, CircularDependencyError
from .discovery import ServiceDiscovery
from .health import ServiceHealth, HealthState
from .events import ServiceEventPublisher, ServiceEventType

__all__ = [
    "ServiceScope",
    "ServiceLifecycle",
    "ServiceMetadata",
    "ServiceContext",
    "BaseService",
    "RuntimeServiceRegistry",
    "ServiceContainer",
    "CircularDependencyError",
    "ServiceDiscovery",
    "ServiceHealth",
    "HealthState",
    "ServiceEventPublisher",
    "ServiceEventType",
]

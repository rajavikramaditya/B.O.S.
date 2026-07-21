"""B.O.S. Runtime Service Registry v0.1

Central registry storing and resolving services by name or interface.
Supports Singleton and Transient lifecycles. Zero hardcoded services.
"""

from typing import Any, Dict, List, Optional, Type
from .base_service import BaseService
from .service_scope import ServiceScope
from .service_lifecycle import ServiceLifecycle
from .events import ServiceEventPublisher, ServiceEventType


class RuntimeServiceRegistry:
    """Stores and manages system service registrations."""

    _services: Dict[str, BaseService] = {}
    _factories: Dict[str, Type[BaseService]] = {}

    @classmethod
    def register(cls, service: BaseService) -> None:
        name = service.metadata.name.lower()
        cls._services[name] = service
        service.status = ServiceLifecycle.REGISTERED
        ServiceEventPublisher.publish(ServiceEventType.SERVICE_REGISTERED, name)

    @classmethod
    def register_factory(cls, name: str, factory_cls: Type[BaseService]) -> None:
        cls._factories[name.lower()] = factory_cls
        ServiceEventPublisher.publish(ServiceEventType.SERVICE_REGISTERED, name)

    @classmethod
    def resolve(cls, name: str) -> Optional[BaseService]:
        name_lower = name.lower()
        # Check singleton instance
        if name_lower in cls._services:
            svc = cls._services[name_lower]
            ServiceEventPublisher.publish(ServiceEventType.SERVICE_RESOLVED, name_lower)
            return svc

        # Check transient factory
        if name_lower in cls._factories:
            factory = cls._factories[name_lower]
            svc = factory()
            ServiceEventPublisher.publish(ServiceEventType.SERVICE_RESOLVED, name_lower)
            return svc

        return None

    @classmethod
    def replace(cls, name: str, new_service: BaseService) -> None:
        name_lower = name.lower()
        old_svc = cls._services.get(name_lower)
        if old_svc:
            old_svc.stop()
        cls._services[name_lower] = new_service
        new_service.status = ServiceLifecycle.REGISTERED
        ServiceEventPublisher.publish(ServiceEventType.SERVICE_REPLACED, name_lower)

    @classmethod
    def unregister(cls, name: str) -> bool:
        name_lower = name.lower()
        svc = cls._services.get(name_lower)
        if svc:
            svc.stop()
            del cls._services[name_lower]
            ServiceEventPublisher.publish(ServiceEventType.SERVICE_STOPPED, name_lower)
            return True
        if name_lower in cls._factories:
            del cls._factories[name_lower]
            return True
        return False

    @classmethod
    def list_services(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": svc.metadata.name,
                "version": svc.metadata.version,
                "scope": svc.metadata.scope.value,
                "status": svc.status.value,
            }
            for svc in cls._services.values()
        ]

    @classmethod
    def clear(cls) -> None:
        for svc in list(cls._services.values()):
            svc.stop()
        cls._services.clear()
        cls._factories.clear()

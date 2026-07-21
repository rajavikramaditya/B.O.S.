"""Tests for TASK-035 to TASK-041: Service Layer & Dependency Injection."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core.services import (
    RuntimeServiceRegistry,
    ServiceContainer,
    ServiceDiscovery,
    ServiceLifecycle,
    CircularDependencyError,
    BaseService,
    ServiceMetadata,
    ServiceContext,
)
from core.services.reference import ClockService


class DependentService(BaseService):
    def __init__(self, name: str = "dependent_service"):
        meta = ServiceMetadata(
            name=name,
            version="1.0.0",
            dependencies=["clock_service"],
        )
        super().__init__(meta)

    def start(self, context: ServiceContext) -> bool:
        self.status = ServiceLifecycle.RUNNING
        return True

    def stop(self) -> bool:
        self.status = ServiceLifecycle.STOPPED
        return True

    def health_check(self) -> dict:
        return {"status": self.status.value}


def setup_function():
    RuntimeServiceRegistry.clear()


def test_service_registration_discovery_and_health():
    clock = ClockService()
    RuntimeServiceRegistry.register(clock)

    assert ServiceDiscovery.is_service_available("clock_service") is True
    resolved = ServiceDiscovery.get_service("clock_service")

    assert resolved is not None
    assert resolved.status == ServiceLifecycle.RUNNING
    assert isinstance(resolved.get_timestamp(), float)

    health = resolved.health_check()
    assert health["readiness"] is True


def test_dependency_injection_and_circular_detection():
    clock = ClockService()
    dep_svc = DependentService()

    RuntimeServiceRegistry.register(clock)
    RuntimeServiceRegistry.register(dep_svc)

    # Container resolves dependent_service and its dependency (clock_service)
    resolved_dep = ServiceContainer.resolve_with_dependencies("dependent_service")
    assert resolved_dep.status == ServiceLifecycle.RUNNING
    assert clock.status == ServiceLifecycle.RUNNING


def test_service_replacement():
    clock1 = ClockService("clock_service")
    RuntimeServiceRegistry.register(clock1)

    class FastClockService(ClockService):
        def get_timestamp(self) -> float:
            return 999.0

    clock2 = FastClockService("clock_service")
    RuntimeServiceRegistry.replace("clock_service", clock2)

    resolved = ServiceDiscovery.get_service("clock_service")
    assert resolved.get_timestamp() == 999.0

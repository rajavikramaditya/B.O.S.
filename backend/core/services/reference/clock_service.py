"""B.O.S. Reference Clock Service v0.1

Minimal reference service demonstrating registration, resolution, DI, health, and replacement.
Zero business logic.
"""

import time
from typing import Any, Dict
from ..base_service import BaseService
from ..service_metadata import ServiceMetadata
from ..service_context import ServiceContext
from ..service_lifecycle import ServiceLifecycle


class ClockService(BaseService):
    """Reference implementation of a platform system service."""

    def __init__(self, name: str = "clock_service"):
        meta = ServiceMetadata(
            name=name,
            version="1.0.0",
            description="Reference clock service providing system timestamps.",
        )
        super().__init__(meta)

    def start(self, context: ServiceContext) -> bool:
        self.context = context
        self.status = ServiceLifecycle.RUNNING
        return True

    def stop(self) -> bool:
        self.status = ServiceLifecycle.STOPPED
        return True

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "liveness": True,
            "readiness": self.status == ServiceLifecycle.RUNNING,
        }

    def get_timestamp(self) -> float:
        return time.time()

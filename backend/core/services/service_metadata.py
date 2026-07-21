"""B.O.S. Service Metadata v0.1

Metadata describing service properties, scope, and dependencies.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from .service_scope import ServiceScope


@dataclass
class ServiceMetadata:
    """Metadata describing a system service."""
    name: str
    version: str = "1.0.0"
    scope: ServiceScope = ServiceScope.SINGLETON
    dependencies: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "scope": self.scope.value,
            "dependencies": self.dependencies,
            "description": self.description,
        }

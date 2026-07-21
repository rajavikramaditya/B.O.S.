"""B.O.S. Capability Metadata v0.1

Describes a platform capability's identity, dependencies, and permissions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .capability_scope import CapabilityScope
from .capability_lifecycle import CapabilityLifecycle


@dataclass
class CapabilityMetadata:
    """Immutable descriptor for a platform capability."""

    # Identity
    name: str
    version: str = "1.0.0"
    category: str = "general"
    description: str = ""

    # Dependencies
    required_providers: List[str] = field(default_factory=list)
    required_services: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # Permissions and access
    permissions: List[str] = field(default_factory=list)
    scope: CapabilityScope = CapabilityScope.GLOBAL

    # Configuration schema (key → default value)
    configuration: Dict[str, Any] = field(default_factory=dict)

    # Runtime state (mutable by registry)
    lifecycle: CapabilityLifecycle = CapabilityLifecycle.UNREGISTERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "required_providers": self.required_providers,
            "required_services": self.required_services,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "scope": self.scope.value,
            "configuration": self.configuration,
            "lifecycle": self.lifecycle.value,
        }

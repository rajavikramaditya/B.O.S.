"""B.O.S. Provider Metadata v0.1

Metadata dataclass defining provider name, capability, priority, and configuration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from .provider_scope import ProviderScope


@dataclass
class ProviderMetadata:
    """Metadata describing a platform technology provider."""

    name: str
    version: str = "1.0.0"
    capability: str = ""
    priority: int = 100
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    scope: ProviderScope = ProviderScope.SINGLETON

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "capability": self.capability,
            "priority": self.priority,
            "description": self.description,
            "dependencies": self.dependencies,
            "config": self.config,
            "scope": self.scope.value if hasattr(self.scope, "value") else self.scope,
        }

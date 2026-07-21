"""B.O.S. Configuration Metadata v0.1

Metadata dataclass describing configuration key, scope, version, and source.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from .configuration_scope import ConfigurationScope
from .configuration_source import ConfigurationSource


@dataclass
class ConfigurationMetadata:
    """Metadata describing a configuration instance."""

    name: str
    scope: ConfigurationScope = ConfigurationScope.GLOBAL
    source: ConfigurationSource = ConfigurationSource.MEMORY
    version: str = "1.0.0"
    tenant_id: str | None = None
    module_id: str | None = None
    provider_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope.value if hasattr(self.scope, "value") else self.scope,
            "source": self.source.value if hasattr(self.source, "value") else self.source,
            "version": self.version,
            "tenant_id": self.tenant_id,
            "module_id": self.module_id,
            "provider_id": self.provider_id,
        }

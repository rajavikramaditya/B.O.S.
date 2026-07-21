"""B.O.S. Provider Manifest Parser v0.1

Parses and validates provider.json and provider.yaml manifest specifications.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List
import yaml
from .provider_metadata import ProviderMetadata
from .provider_scope import ProviderScope


@dataclass
class ProviderManifest:
    """Dataclass holding validated provider manifest fields."""

    name: str
    version: str = "1.0.0"
    capability: str = ""
    priority: int = 100
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    configuration: Dict[str, Any] = field(default_factory=dict)
    health_endpoint: str = ""
    scope: str = "SINGLETON"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderManifest":
        if "name" not in data or not data["name"]:
            raise ValueError("Provider manifest must specify 'name'.")
        if "capability" not in data or not data["capability"]:
            raise ValueError("Provider manifest must specify 'capability'.")

        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            capability=data["capability"],
            priority=int(data.get("priority", 100)),
            description=data.get("description", ""),
            dependencies=data.get("dependencies", []),
            configuration=data.get("configuration", {}),
            health_endpoint=data.get("health_endpoint", ""),
            scope=data.get("scope", "SINGLETON").upper(),
        )

    @classmethod
    def from_json(cls, content: str) -> "ProviderManifest":
        data = json.loads(content)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, content: str) -> "ProviderManifest":
        data = yaml.safe_load(content)
        return cls.from_dict(data)

    def to_metadata(self) -> ProviderMetadata:
        try:
            scope_enum = ProviderScope(self.scope)
        except ValueError:
            scope_enum = ProviderScope.SINGLETON

        return ProviderMetadata(
            name=self.name,
            version=self.version,
            capability=self.capability,
            priority=self.priority,
            description=self.description,
            dependencies=self.dependencies,
            config=self.configuration,
            scope=scope_enum,
        )

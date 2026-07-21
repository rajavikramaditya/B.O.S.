"""B.O.S. Capability Manifest Parser v0.1

Parses and validates capability.json and capability.yaml manifest specifications.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

from .capability_metadata import CapabilityMetadata
from .capability_scope import CapabilityScope


@dataclass
class CapabilityManifest:
    """Parsed and validated capability manifest."""

    name: str
    version: str = "1.0.0"
    category: str = "general"
    description: str = ""

    # Dependencies
    required_providers: List[str] = field(default_factory=list)
    required_services: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # Access control
    permissions: List[str] = field(default_factory=list)
    scope: str = "GLOBAL"

    # Configuration schema
    configuration: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityManifest":
        """Parse a manifest from a dictionary."""
        if "name" not in data or not data["name"]:
            raise ValueError("Capability manifest must specify 'name'.")

        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            category=data.get("category", "general"),
            description=data.get("description", ""),
            required_providers=data.get("required_providers", []),
            required_services=data.get("required_services", []),
            dependencies=data.get("dependencies", []),
            permissions=data.get("permissions", []),
            scope=data.get("scope", "GLOBAL").upper(),
            configuration=data.get("configuration", {}),
        )

    @classmethod
    def from_json(cls, content: str) -> "CapabilityManifest":
        """Parse a manifest from a JSON string."""
        data = json.loads(content)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, content: str) -> "CapabilityManifest":
        """Parse a manifest from a YAML string."""
        data = yaml.safe_load(content)
        return cls.from_dict(data)

    def to_metadata(self) -> CapabilityMetadata:
        """Convert manifest to CapabilityMetadata for runtime registration."""
        try:
            scope_enum = CapabilityScope(self.scope)
        except ValueError:
            scope_enum = CapabilityScope.GLOBAL

        return CapabilityMetadata(
            name=self.name,
            version=self.version,
            category=self.category,
            description=self.description,
            required_providers=self.required_providers,
            required_services=self.required_services,
            dependencies=self.dependencies,
            permissions=self.permissions,
            scope=scope_enum,
            configuration=self.configuration,
        )

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
            "scope": self.scope,
            "configuration": self.configuration,
        }

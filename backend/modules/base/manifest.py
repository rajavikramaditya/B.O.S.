"""B.O.S. Module Manifest v0.1

Data model and validation parser for module.json / module.yaml manifests.
Manifest must be validated before loading any module.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ModuleManifest:
    """Standardized manifest structure for installable B.O.S. modules."""
    name: str
    version: str = "1.0.0"
    author: str = "Unknown"
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    business_objects: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    configuration: Dict[str, Any] = field(default_factory=dict)
    required_providers: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    validation_rules: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModuleManifest":
        """Parse dictionary and validate required manifest fields."""
        if not data.get("name"):
            raise ValueError("ModuleManifest validation error: 'name' field is required.")
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Unknown"),
            description=data.get("description", ""),
            capabilities=data.get("capabilities", []),
            business_objects=data.get("business_objects", []),
            permissions=data.get("permissions", []),
            dependencies=data.get("dependencies", []),
            configuration=data.get("configuration", {}),
            required_providers=data.get("required_providers", []),
            settings=data.get("settings", {}),
            validation_rules=data.get("validation_rules", []),
        )

    def validate(self) -> bool:
        """Validate manifest integrity."""
        if not self.name or not isinstance(self.name, str):
            return False
        if not self.version or not isinstance(self.version, str):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "capabilities": self.capabilities,
            "business_objects": self.business_objects,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "configuration": self.configuration,
            "required_providers": self.required_providers,
            "settings": self.settings,
            "validation_rules": self.validation_rules,
        }

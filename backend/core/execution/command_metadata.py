"""B.O.S. Command Metadata v0.1

Metadata dataclass describing command properties, name, description, and permission requirements.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CommandMetadata:
    """Metadata describing a platform command."""
    name: str
    description: str = ""
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_permissions": self.required_permissions,
            "timeout_seconds": self.timeout_seconds,
        }

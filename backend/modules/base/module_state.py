"""B.O.S. Module State v0.1

Container object tracking runtime module state and settings.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from .module_lifecycle import ModuleLifecycle


@dataclass
class ModuleState:
    """Runtime operational state of an installed module."""
    status: ModuleLifecycle = ModuleLifecycle.UNLOADED
    active: bool = False
    configuration: Dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "active": self.active,
            "configuration": self.configuration,
            "error_message": self.error_message,
        }

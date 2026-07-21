"""B.O.S. Module Context v0.1

Execution context injected into modules by the Module Loader.
Provides safe public access to platform capabilities, event bus, and policy engine.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ModuleContext:
    """Injected runtime context for business modules."""
    module_id: str
    event_bus: Any = None
    capability_registry: Any = None
    policy_engine: Any = None
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "has_event_bus": self.event_bus is not None,
            "has_capability_registry": self.capability_registry is not None,
            "has_policy_engine": self.policy_engine is not None,
            "settings": self.settings,
        }

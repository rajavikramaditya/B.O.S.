"""B.O.S. Provider Context v0.1

Execution context passed to providers carrying services, execution tokens, and environment options.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderContext:
    """Context object passed to BaseProvider during initialization and execution."""

    provider_id: str
    services: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    environment: str = "production"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "environment": self.environment,
            "config": self.config,
        }

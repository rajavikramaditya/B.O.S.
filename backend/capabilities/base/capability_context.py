"""B.O.S. Capability Context v0.1

Execution context injected into every capability execution call.
Carries tenant, module, correlation, and feature flag information.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CapabilityContext:
    """Runtime context passed to every capability execution."""

    # Identity
    tenant_id: str = "default"
    module_id: str = ""
    correlation_id: str = field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:12]}")

    # Feature flags active for this execution
    feature_flags: List[str] = field(default_factory=list)

    # Configuration overrides for this execution
    configuration: Dict[str, Any] = field(default_factory=dict)

    # Additional metadata
    extra: Dict[str, Any] = field(default_factory=dict)

    # Timestamp
    created_at: float = field(default_factory=time.time)

    def has_flag(self, flag: str) -> bool:
        """Check if a feature flag is active in this context."""
        return flag in self.feature_flags

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with optional default."""
        return self.configuration.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "module_id": self.module_id,
            "correlation_id": self.correlation_id,
            "feature_flags": self.feature_flags,
            "configuration": self.configuration,
            "extra": self.extra,
            "created_at": self.created_at,
        }

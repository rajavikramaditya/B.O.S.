"""B.O.S. Configuration Context v0.1

Execution context carrying active scope IDs (tenant_id, module_id, provider_id) during configuration resolution.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ConfigurationContext:
    """Context object carrying active IDs during configuration lookup."""

    tenant_id: Optional[str] = None
    module_id: Optional[str] = None
    provider_id: Optional[str] = None
    environment: str = "production"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "module_id": self.module_id,
            "provider_id": self.provider_id,
            "environment": self.environment,
        }

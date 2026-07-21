"""B.O.S. Capability Metadata Specification v0.1

Defines metadata schema for universal platform capabilities.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CapabilityMetadata:
    """Metadata describing a platform capability, its parameters, policies, and adapters."""
    name: str
    description: str
    required_inputs: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    supported_adapters: List[str] = field(default_factory=list)
    execution_strategy: str = "direct"  # "direct", "async", "retryable"
    retry_policy: Dict[str, Any] = field(
        default_factory=lambda: {"max_retries": 3, "backoff_seconds": 1.0}
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_inputs": self.required_inputs,
            "expected_outputs": self.expected_outputs,
            "required_permissions": self.required_permissions,
            "supported_adapters": self.supported_adapters,
            "execution_strategy": self.execution_strategy,
            "retry_policy": self.retry_policy,
        }

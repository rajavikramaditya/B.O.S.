"""B.O.S. Capability Result v0.1

Normalized output envelope returned by every capability execution.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CapabilityResult:
    """Standard output envelope returned by all capability executions."""

    # Core fields
    success: bool
    capability_name: str
    action: str

    # Payload
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: Optional[str] = None

    # Traceability
    provider_used: Optional[str] = None
    correlation_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamp
    completed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "capability_name": self.capability_name,
            "action": self.action,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "provider_used": self.provider_used,
            "correlation_id": self.correlation_id,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
            "completed_at": self.completed_at,
        }

    @classmethod
    def failure(
        cls,
        capability_name: str,
        action: str,
        error: str,
        correlation_id: Optional[str] = None,
    ) -> "CapabilityResult":
        """Factory for failure results."""
        return cls(
            success=False,
            capability_name=capability_name,
            action=action,
            error=error,
            correlation_id=correlation_id,
        )

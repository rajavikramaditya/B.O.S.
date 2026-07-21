"""B.O.S. Command Result v0.1

Standardized output container returned by command execution.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from .execution_state import ExecutionState


@dataclass
class CommandResult:
    """Output container produced by command pipeline execution."""
    success: bool
    state: ExecutionState | str = ExecutionState.COMPLETED
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "state": str(self.state.value if hasattr(self.state, "value") else self.state),
            "data": self.data,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
        }

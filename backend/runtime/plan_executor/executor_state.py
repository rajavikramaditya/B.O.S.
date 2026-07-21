"""B.O.S. Plan Executor State v0.1

State and status models for step-by-step plan execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutorStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


@dataclass
class ExecutorState:
    """Tracks current step index, status, completed steps, and execution checkpoints."""
    current_step_index: int = 0
    status: ExecutorStatus | str = ExecutorStatus.IDLE
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)
    failed_steps: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_step_index": self.current_step_index,
            "status": str(self.status.value if hasattr(self.status, "value") else self.status),
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "checkpoints": self.checkpoints,
            "execution_result": self.execution_result,
            "cancel_requested": self.cancel_requested,
        }


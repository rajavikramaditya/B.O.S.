"""B.O.S. Orchestrator State v0.1

State model tracking which reasoning and execution engines participate in a run.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OrchestratorState:
    """State tracking active engines and reasoning steps during orchestration."""
    participating_engines: List[str] = field(default_factory=list)
    active_step: str = "INIT"
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_steps: List[str] = field(default_factory=list)

    def mark_completed(self, step: str) -> None:
        self.completed_steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "participating_engines": self.participating_engines,
            "active_step": self.active_step,
            "metadata": self.metadata,
            "completed_steps": self.completed_steps,
        }

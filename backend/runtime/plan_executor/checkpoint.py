"""B.O.S. Plan Checkpoint v0.1

State snapshot container for plan recovery and rollback.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PlanCheckpoint:
    """Snapshot of plan state at a specific step index."""
    step_index: int
    snapshot_data: Dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str = field(default_factory=lambda: f"chk_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "step_index": self.step_index,
            "snapshot_data": self.snapshot_data,
        }

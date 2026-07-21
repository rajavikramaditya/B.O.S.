"""B.O.S. Rollback Handler v0.1

Handles step failure rollback and checkpoint restoration.
"""

from typing import Any, Dict, Optional
from .executor_state import ExecutorState, ExecutorStatus
from .checkpoint import PlanCheckpoint


class RollbackHandler:
    """Restores plan state from checkpoints upon step failure."""

    @classmethod
    def rollback(cls, state: ExecutorState, target_checkpoint_id: str | None = None) -> ExecutorState:
        if target_checkpoint_id and target_checkpoint_id in state.checkpoints:
            chk_data = state.checkpoints[target_checkpoint_id]
            state.current_step_index = chk_data.get("step_index", 0)
            state.status = ExecutorStatus.ROLLED_BACK
        elif state.checkpoints:
            # Rollback to latest checkpoint
            latest_chk_id = list(state.checkpoints.keys())[-1]
            chk_data = state.checkpoints[latest_chk_id]
            state.current_step_index = chk_data.get("step_index", 0)
            state.status = ExecutorStatus.ROLLED_BACK
        else:
            state.current_step_index = 0
            state.status = ExecutorStatus.ROLLED_BACK

        return state

"""B.O.S. Plan Executor Facade v0.1

Facade coordinating step-by-step execution, pauses, resumes, retries, skips,
rollbacks, checkpoints, and recoveries.
"""

from typing import Any, Dict, List, Optional
from ..contracts import ExecutionPlan, PlanStep
from .executor_state import ExecutorState, ExecutorStatus
from .checkpoint import PlanCheckpoint
from .rollback import RollbackHandler
from .step_runner import StepRunner


class PlanExecutor:
    """Orchestrates plan step execution, checkpointing, recovery, and pause/resume."""

    @classmethod
    def execute_plan(
        cls,
        plan: ExecutionPlan,
        role: str = "customer",
        existing_state: Optional[ExecutorState] = None,
    ) -> ExecutorState:
        state = existing_state or ExecutorState()
        state.status = ExecutorStatus.RUNNING

        steps = plan.steps or []
        while state.current_step_index < len(steps):
            idx = state.current_step_index
            step = steps[idx]

            # Save checkpoint before step
            chk = PlanCheckpoint(step_index=idx, snapshot_data={"action": step.action})
            state.checkpoints[chk.checkpoint_id] = chk.to_dict()

            res = StepRunner.run_step(step, state, role)

            if state.status == ExecutorStatus.WAITING_APPROVAL:
                break

            if res.get("status") == "SUCCESS":
                state.completed_steps.append({"step_index": idx, "action": step.action, "res": res})
                state.current_step_index += 1
            else:
                state.failed_steps.append({"step_index": idx, "action": step.action, "res": res})
                # Attempt rollback or retry
                RollbackHandler.rollback(state)
                break

        if state.current_step_index >= len(steps) and state.status == ExecutorStatus.RUNNING:
            state.status = ExecutorStatus.COMPLETED

        return state

    @classmethod
    def resume_execution(cls, plan: ExecutionPlan, state: ExecutorState, role: str = "owner") -> ExecutorState:
        state.status = ExecutorStatus.RUNNING
        # If paused at WAITING_APPROVAL, approve and advance
        if state.current_step_index < len(plan.steps):
            step = plan.steps[state.current_step_index]
            if step.params:
                step.params["requires_approval"] = False
        return cls.execute_plan(plan, role=role, existing_state=state)

    @classmethod
    def skip_step(cls, plan: ExecutionPlan, state: ExecutorState) -> ExecutorState:
        if state.current_step_index < len(plan.steps):
            state.completed_steps.append({
                "step_index": state.current_step_index,
                "action": plan.steps[state.current_step_index].action,
                "skipped": True,
            })
            state.current_step_index += 1
        return cls.execute_plan(plan, existing_state=state)

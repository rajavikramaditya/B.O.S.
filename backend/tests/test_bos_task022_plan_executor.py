"""Tests for TASK-022: Plan Executor."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.contracts import ExecutionPlan, PlanStep
from runtime.plan_executor import PlanExecutor, ExecutorState, ExecutorStatus


def test_plan_executor_normal_flow():
    plan = ExecutionPlan(
        plan_id="plan_1",
        intent_type="messaging",
        steps=[
            PlanStep(step_id="s1", capability="messaging", action="send_message", params={"text": "Step 1"}),
            PlanStep(step_id="s2", capability="scheduling", action="schedule_meeting", params={"title": "Step 2"}),
        ],
    )
    state = PlanExecutor.execute_plan(plan)
    assert isinstance(state, ExecutorState)
    assert state.status == ExecutorStatus.COMPLETED
    assert len(state.completed_steps) == 2
    assert len(state.checkpoints) == 2


def test_plan_executor_approval_pause_and_resume():
    plan = ExecutionPlan(
        plan_id="plan_2",
        intent_type="protected_command",
        steps=[
            PlanStep(step_id="s1", capability="automation", action="send_azuracast", params={"requires_approval": True}),
            PlanStep(step_id="s2", capability="messaging", action="send_message", params={"text": "Completed"}),
        ],
    )
    state = PlanExecutor.execute_plan(plan, role="owner")
    assert state.status == ExecutorStatus.WAITING_APPROVAL
    assert state.current_step_index == 0

    # Resume execution after approval
    resumed_state = PlanExecutor.resume_execution(plan, state, role="owner")
    assert resumed_state.status == ExecutorStatus.COMPLETED
    assert len(resumed_state.completed_steps) == 2

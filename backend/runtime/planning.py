"""B.O.S. Planning Engine v1.0

Stage 5 of Runtime Lifecycle: Turns the proposed steps into a validated ExecutionPlan.
Each step carries the risk declared by its capability, never a guessed one.
"""

import uuid
from typing import Any

from .cognition import RuntimeCognition
from .contracts import BusinessIntent, ExecutionPlan, ExecutionPlanStep

MAX_STEPS = 8


class PlanningEngine:
    """Creates step-by-step execution plans from business goals."""

    @staticmethod
    def create_plan(intent: BusinessIntent, strategy: Any = None) -> ExecutionPlan:
        steps = []
        for index, proposed in enumerate(intent.proposed_steps[:MAX_STEPS], start=1):
            capability = proposed.get("capability", "")
            action = proposed.get("action", "")
            risk = RuntimeCognition.action_risk(capability, action) or "unknown"
            steps.append(
                ExecutionPlanStep(
                    step_id=index,
                    action=action,
                    capability=capability,
                    params=dict(proposed.get("params") or {}),
                    title=proposed.get("title") or f"{capability}.{action}",
                    reason=proposed.get("reason", ""),
                    risk=risk,
                    continue_on_failure=True,
                )
            )
        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:10]}",
            intent_type=intent.intent_type,
            goal=intent.goal,
            steps=steps,
            requires_approval=False,
        )

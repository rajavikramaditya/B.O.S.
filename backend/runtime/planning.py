"""B.O.S. Planning Engine v0.1

Stage 5 of Runtime Lifecycle: Transforms reasoning strategy into step-by-step ExecutionPlan.
"""

import uuid
from .contracts import (
    BusinessIntent,
    ReasoningStrategy,
    ExecutionPlan,
    ExecutionPlanStep,
)


class PlanningEngine:
    """Creates step-by-step execution plans from business goals."""

    @staticmethod
    def create_plan(intent: BusinessIntent, strategy: ReasoningStrategy) -> ExecutionPlan:
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        steps = [
            ExecutionPlanStep(
                step_id=1,
                capability=cap,
                action=intent.action,
                params=intent.slots,
            )
            for cap in strategy.target_capabilities
        ]
        return ExecutionPlan(
            plan_id=plan_id,
            goal=intent.goal,
            steps=steps,
            requires_confirmation=False,
        )

"""B.O.S. Goal Breakdown Engine v0.1

Decomposes high-level business goals into Milestones, Sub-Goals, Workflow Plans, and Execution Units.
"""

from typing import List, Dict, Any
from .goal import Goal
from .goal_state import GoalState


class GoalBreakdownEngine:
    """Decomposes goals into actionable milestones and sub-goal execution units."""

    @classmethod
    def breakdown(cls, goal: Goal) -> Goal:
        title_lower = goal.title.lower()

        milestones = [
            {"id": "m1", "title": "Feasibility & Policy Evaluation", "completed": False},
            {"id": "m2", "title": "Workflow Graph Plan Formulation", "completed": False},
            {"id": "m3", "title": "Capability & Resource Allocation", "completed": False},
            {"id": "m4", "title": "Execution & Verification", "completed": False},
        ]

        sub_goals = [f"SubGoal 1 for {goal.title}", f"SubGoal 2 for {goal.title}"]
        plans = [f"WorkflowPlan_{goal.goal_id[:8]}"]

        units = [
            {"unit_id": "u1", "milestone_id": "m1", "action": "policy_check", "status": "PENDING"},
            {"unit_id": "u2", "milestone_id": "m2", "action": "build_graph", "status": "PENDING"},
            {"unit_id": "u3", "milestone_id": "m3", "action": "select_caps", "status": "PENDING"},
            {"unit_id": "u4", "milestone_id": "m4", "action": "execute_and_verify", "status": "PENDING"},
        ]

        goal.milestones = milestones
        goal.sub_goals = sub_goals
        goal.workflow_plans = plans
        goal.execution_units = units
        goal.state = GoalState.IN_PROGRESS
        return goal

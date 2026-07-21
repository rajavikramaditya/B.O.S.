"""B.O.S. Goal Progress Tracker v0.1

Tracks execution unit progress and calculates goal completion percentages.
"""

from typing import Any, Dict
from .goal import Goal
from .goal_state import GoalState


class GoalProgressTracker:
    """Calculates completion metrics and updates goal states."""

    @classmethod
    def update_unit_status(cls, goal: Goal, unit_id: str, status: str) -> Goal:
        for unit in goal.execution_units:
            if unit.get("unit_id") == unit_id:
                unit["status"] = status
                break

        completed_count = sum(1 for u in goal.execution_units if u.get("status") == "COMPLETED")
        total = len(goal.execution_units) or 1
        goal.progress_percentage = round((completed_count / total) * 100.0, 1)

        if completed_count == total:
            goal.state = GoalState.COMPLETED
            for m in goal.milestones:
                m["completed"] = True

        return goal

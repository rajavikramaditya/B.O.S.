"""B.O.S. Goal Manager v0.1

Facade for creating, decomposing, tracking, and updating business goals.
Manages goals; does NOT execute.
"""

from typing import Any, Dict, List, Optional
from .goal import Goal
from .goal_state import GoalState
from .goal_breakdown import GoalBreakdownEngine
from .goal_progress import GoalProgressTracker


class GoalManager:
    """Manages high-level goal breakdown, milestone tracking, and state progress."""

    _active_goals: Dict[str, Goal] = {}

    @classmethod
    def create_goal(cls, title: str, description: str = "") -> Goal:
        goal = Goal(title=title, description=description)
        goal = GoalBreakdownEngine.breakdown(goal)
        cls._active_goals[goal.goal_id] = goal
        return goal

    @classmethod
    def get_goal(cls, goal_id: str) -> Optional[Goal]:
        return cls._active_goals.get(goal_id)

    @classmethod
    def update_progress(cls, goal_id: str, unit_id: str, status: str) -> Optional[Goal]:
        goal = cls.get_goal(goal_id)
        if goal:
            return GoalProgressTracker.update_unit_status(goal, unit_id, status)
        return None

    @classmethod
    def clear(cls) -> None:
        cls._active_goals.clear()

"""B.O.S. Goal Model v0.1

Container representing a high-level business goal, its milestones, sub-goals, and execution units.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List
from .goal_state import GoalState


@dataclass
class Goal:
    """High-level business goal container."""
    title: str
    description: str = ""
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    sub_goals: List[str] = field(default_factory=list)
    workflow_plans: List[str] = field(default_factory=list)
    execution_units: List[Dict[str, Any]] = field(default_factory=list)
    state: GoalState | str = GoalState.CREATED
    progress_percentage: float = 0.0
    goal_id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "milestones": self.milestones,
            "sub_goals": self.sub_goals,
            "workflow_plans": self.workflow_plans,
            "execution_units": self.execution_units,
            "state": str(self.state.value if hasattr(self.state, "value") else self.state),
            "progress_percentage": self.progress_percentage,
        }

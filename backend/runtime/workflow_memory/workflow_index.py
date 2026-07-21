"""B.O.S. Workflow Index v0.1

Indexes workflow patterns by goal, intent, and success rate.
"""

from typing import Any, Dict, List, Optional
from .pattern_store import PatternStore


class WorkflowIndex:
    """Search and lookup index for reusable workflow patterns."""

    @classmethod
    def index_pattern(cls, goal: str, pattern_id: str, success_rate: float = 1.0) -> None:
        pattern_data = PatternStore.get_pattern(pattern_id) or {}
        pattern_data.update({
            "pattern_id": pattern_id,
            "goal": goal,
            "success_rate": success_rate,
        })
        PatternStore.save_pattern(pattern_id, pattern_data)

    @classmethod
    def find_matching_pattern(cls, goal: str) -> Optional[Dict[str, Any]]:
        goal_lower = (goal or "").lower()
        patterns = PatternStore.list_patterns()
        for p in patterns:
            p_goal = str(p.get("goal", "")).lower()
            if p_goal and (p_goal in goal_lower or goal_lower in p_goal):
                return p
        return None

"""B.O.S. Goal State Enum v0.1

Enumeration of goal lifecycle states.
"""

from enum import Enum


class GoalState(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

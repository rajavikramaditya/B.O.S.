"""B.O.S. Execution State Enum v0.1

Enumeration of command execution lifecycle states.
"""

from enum import Enum


class ExecutionState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

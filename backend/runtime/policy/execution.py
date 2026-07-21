"""B.O.S. Execution Policy v0.1

Evaluates resource limits, system load, and execution capability constraints.
"""

from typing import Any, Dict


class ExecutionPolicy:
    """Evaluates execution readiness and system resource constraints."""

    @classmethod
    def evaluate(cls, action: str, params: Dict[str, Any]) -> str:
        if params.get("system_overloaded"):
            return "ESCALATE"
        return "ALLOW"

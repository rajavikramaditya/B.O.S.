"""B.O.S. Workflow History Store v0.1

Stores decision history, approval history, and recovery history.
"""

from typing import Any, Dict, List


class HistoryStore:
    """Stores detailed decision, approval, and recovery logs for workflow runs."""

    _decision_history: List[Dict[str, Any]] = []
    _approval_history: List[Dict[str, Any]] = []
    _recovery_history: List[Dict[str, Any]] = []

    @classmethod
    def log_decision(cls, decision_data: Dict[str, Any]) -> None:
        cls._decision_history.append(decision_data)

    @classmethod
    def log_approval(cls, approval_data: Dict[str, Any]) -> None:
        cls._approval_history.append(approval_data)

    @classmethod
    def log_recovery(cls, recovery_data: Dict[str, Any]) -> None:
        cls._recovery_history.append(recovery_data)

    @classmethod
    def get_history(cls, limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "decisions": cls._decision_history[-limit:],
            "approvals": cls._approval_history[-limit:],
            "recoveries": cls._recovery_history[-limit:],
        }

    @classmethod
    def clear(cls) -> None:
        cls._decision_history.clear()
        cls._approval_history.clear()
        cls._recovery_history.clear()

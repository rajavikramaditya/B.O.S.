"""B.O.S. Workflow Store v0.1

Stores completed workflow execution records, successful paths, and failed paths.
"""

from typing import Any, Dict, List, Optional


class WorkflowStore:
    """Stores completed workflow execution states and path outcomes."""

    _successful_paths: List[Dict[str, Any]] = []
    _failed_paths: List[Dict[str, Any]] = []
    _executions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def record_execution(cls, execution_id: str, record: Dict[str, Any]) -> None:
        cls._executions[execution_id] = record
        if record.get("status") == "COMPLETED":
            cls._successful_paths.append(record)
        else:
            cls._failed_paths.append(record)

    @classmethod
    def get_execution(cls, execution_id: str) -> Optional[Dict[str, Any]]:
        return cls._executions.get(execution_id)

    @classmethod
    def get_successful_paths(cls, limit: int = 50) -> List[Dict[str, Any]]:
        return cls._successful_paths[-limit:]

    @classmethod
    def get_failed_paths(cls, limit: int = 50) -> List[Dict[str, Any]]:
        return cls._failed_paths[-limit:]

    @classmethod
    def clear(cls) -> None:
        cls._executions.clear()
        cls._successful_paths.clear()
        cls._failed_paths.clear()

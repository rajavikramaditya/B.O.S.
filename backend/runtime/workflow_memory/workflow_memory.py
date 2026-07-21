"""B.O.S. Workflow Memory Facade v0.1

Unified facade for WorkflowStore, PatternStore, HistoryStore, and WorkflowIndex.
Allows future runtime executions to reuse successful workflow patterns.
"""

from typing import Any, Dict, List, Optional
from .workflow_store import WorkflowStore
from .pattern_store import PatternStore
from .history_store import HistoryStore
from .workflow_index import WorkflowIndex


class WorkflowMemory:
    """Unified access facade for Workflow Memory storage, patterns, history, and lookup."""

    @classmethod
    def record_run(cls, execution_id: str, record: Dict[str, Any]) -> None:
        WorkflowStore.record_execution(execution_id, record)
        goal = record.get("goal") or record.get("intent", {}).get("goal")
        if goal and record.get("status") == "COMPLETED":
            pattern_id = f"pat_{execution_id}"
            pattern_data = {
                "pattern_id": pattern_id,
                "goal": goal,
                "graph_id": record.get("graph_id", "default"),
                "visited_nodes": record.get("visited_nodes", []),
            }
            PatternStore.save_pattern(pattern_id, pattern_data)
            WorkflowIndex.index_pattern(goal, pattern_id, success_rate=1.0)

    @classmethod
    def recall_pattern_for_goal(cls, goal: str) -> Optional[Dict[str, Any]]:
        return WorkflowIndex.find_matching_pattern(goal)

    @classmethod
    def log_decision(cls, decision_data: Dict[str, Any]) -> None:
        HistoryStore.log_decision(decision_data)

    @classmethod
    def log_approval(cls, approval_data: Dict[str, Any]) -> None:
        HistoryStore.log_approval(approval_data)

    @classmethod
    def log_recovery(cls, recovery_data: Dict[str, Any]) -> None:
        HistoryStore.log_recovery(recovery_data)

    @classmethod
    def get_history(cls, limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
        return HistoryStore.get_history(limit=limit)

    @classmethod
    def clear_all(cls) -> None:
        WorkflowStore.clear()
        PatternStore.clear()
        HistoryStore.clear()

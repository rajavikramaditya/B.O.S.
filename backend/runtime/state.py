"""B.O.S. Runtime State Model v0.1

State model tracking execution state, checkpoints, retries, visited nodes,
and human-in-the-loop approvals across the B.O.S. Workflow Graph.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


WorkflowStatus = Literal[
    "INITIALIZED",
    "RUNNING",
    "PAUSED",
    "WAITING_APPROVAL",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]


@dataclass
class ExecutionHistoryEntry:
    node: str
    timestamp: float
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class Checkpoint:
    checkpoint_id: str
    node: str
    timestamp: float
    state_snapshot: Dict[str, Any]


@dataclass
class RuntimeState:
    """Complete execution state for a B.O.S. Workflow Graph run."""
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    current_node: str = "START"
    visited_nodes: List[str] = field(default_factory=list)
    status: WorkflowStatus = "INITIALIZED"
    pending_capability: Optional[str] = None
    pending_action: Optional[str] = None
    pending_params: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    errors: List[Dict[str, Any]] = field(default_factory=list)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[ExecutionHistoryEntry] = field(default_factory=list)
    checkpoints: Dict[str, Checkpoint] = field(default_factory=dict)
    
    # Payload compartments
    request_data: Dict[str, Any] = field(default_factory=dict)
    intent_data: Dict[str, Any] = field(default_factory=dict)
    plan_data: Dict[str, Any] = field(default_factory=dict)
    policy_data: Dict[str, Any] = field(default_factory=dict)
    execution_data: Dict[str, Any] = field(default_factory=dict)
    verification_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, node_name: str, status: WorkflowStatus = "RUNNING") -> None:
        self.visited_nodes.append(self.current_node)
        self.current_node = node_name
        self.status = status
        self.execution_history.append(
            ExecutionHistoryEntry(
                node=node_name,
                timestamp=time.time(),
                status=status,
                data={"pending_action": self.pending_action},
            )
        )

    def record_error(self, error_message: str, node: Optional[str] = None) -> None:
        target_node = node or self.current_node
        self.errors.append({
            "node": target_node,
            "timestamp": time.time(),
            "error": error_message,
        })
        self.retry_count += 1

    def save_checkpoint(self, name: str) -> Checkpoint:
        cp_id = f"cp_{uuid.uuid4().hex[:8]}"
        snapshot = {
            "execution_id": self.execution_id,
            "current_node": self.current_node,
            "visited_nodes": list(self.visited_nodes),
            "status": self.status,
            "pending_capability": self.pending_capability,
            "pending_action": self.pending_action,
            "pending_params": dict(self.pending_params),
            "retry_count": self.retry_count,
            "request_data": dict(self.request_data),
            "intent_data": dict(self.intent_data),
            "plan_data": dict(self.plan_data),
            "policy_data": dict(self.policy_data),
        }
        cp = Checkpoint(
            checkpoint_id=cp_id,
            node=self.current_node,
            timestamp=time.time(),
            state_snapshot=snapshot,
        )
        self.checkpoints[name] = cp
        return cp

    def restore_checkpoint(self, name: str) -> bool:
        if name not in self.checkpoints:
            return False
        cp = self.checkpoints[name]
        snap = cp.state_snapshot
        self.current_node = snap.get("current_node", self.current_node)
        self.visited_nodes = list(snap.get("visited_nodes", self.visited_nodes))
        self.status = snap.get("status", self.status)
        self.pending_capability = snap.get("pending_capability")
        self.pending_action = snap.get("pending_action")
        self.pending_params = dict(snap.get("pending_params", {}))
        self.retry_count = snap.get("retry_count", self.retry_count)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "current_node": self.current_node,
            "visited_nodes": self.visited_nodes,
            "status": self.status,
            "pending_capability": self.pending_capability,
            "pending_action": self.pending_action,
            "retry_count": self.retry_count,
            "errors": self.errors,
            "request_data": self.request_data,
            "response_data": self.response_data,
        }

"""B.O.S. Execution Transaction Context v0.1

Provides correlation IDs, parent/child execution relationships, and transaction tracking.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionTransaction:
    """Transaction context tracking nested execution runs across the CommandBus."""
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    parent_execution_id: Optional[str] = None
    nested_executions: List[str] = field(default_factory=list)

    def create_nested_transaction(self) -> "ExecutionTransaction":
        child_id = f"exec_{uuid.uuid4().hex[:12]}"
        self.nested_executions.append(child_id)
        return ExecutionTransaction(
            correlation_id=self.correlation_id,
            execution_id=child_id,
            parent_execution_id=self.execution_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "nested_executions": self.nested_executions,
        }

"""B.O.S. Execution Context Container v0.1

Universal execution container encapsulating actor, permissions, memory, knowledge,
workflow, and runtime state. Passed across runtime components to eliminate argument sprawl.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from ..state import RuntimeState


@dataclass
class ExecutionContext:
    """Universal execution context container for a B.O.S. runtime run."""
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    business_id: str = "default_organization"
    actor: str = "user"
    role: str = "customer"  # "owner", "customer", "employee"
    permissions: List[str] = field(default_factory=list)
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    knowledge_context: Dict[str, Any] = field(default_factory=dict)
    workflow_context: Dict[str, Any] = field(default_factory=dict)
    capability_context: Dict[str, Any] = field(default_factory=dict)
    runtime_state: Optional[RuntimeState] = None

    def has_permission(self, permission: str) -> bool:
        if "*" in self.permissions or "admin" in self.permissions:
            return True
        return permission in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "business_id": self.business_id,
            "actor": self.actor,
            "role": self.role,
            "permissions": self.permissions,
            "conversation_context": self.conversation_context,
            "memory_context": self.memory_context,
            "knowledge_context": self.knowledge_context,
            "workflow_context": self.workflow_context,
            "capability_context": self.capability_context,
            "runtime_state": self.runtime_state.to_dict() if self.runtime_state else None,
        }

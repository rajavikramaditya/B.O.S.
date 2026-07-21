"""B.O.S. Command Context v0.1

Execution context passed to commands containing parameters, actor info, and transaction reference.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CommandContext:
    """Context object carrying input parameters and actor identity for command execution."""
    command_id: str
    actor_id: str = "system"
    role: str = "customer"
    params: Dict[str, Any] = field(default_factory=dict)
    transaction_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "actor_id": self.actor_id,
            "role": self.role,
            "params": self.params,
            "transaction_id": self.transaction_id,
        }

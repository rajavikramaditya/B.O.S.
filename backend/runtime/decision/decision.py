"""B.O.S. Decision Result Model v0.1

Data model for reasoning decisions returned by the Decision Engine.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionResult:
    """Evaluation result produced by DecisionEngine."""
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (critical)
    risk_level: str = "LOW"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    business_approval_required: bool = False
    can_auto_execute: bool = True
    recommended_action: str = "execute"  # "execute", "confirm", "deny", "escalate"
    retry_decision: Dict[str, Any] = field(
        default_factory=lambda: {"should_retry": False, "max_retries": 3, "backoff_seconds": 1.0}
    )
    fallback_decision: Optional[Dict[str, Any]] = None
    execution_priority: int = 1  # Higher number = higher priority
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "business_approval_required": self.business_approval_required,
            "can_auto_execute": self.can_auto_execute,
            "recommended_action": self.recommended_action,
            "retry_decision": self.retry_decision,
            "fallback_decision": self.fallback_decision,
            "execution_priority": self.execution_priority,
            "notes": self.notes,
        }

"""B.O.S. IntentObject Model v0.1

Container representing analyzed business intent, goals, constraints, priority, and required capabilities.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List
from .intent_types import IntentCategory, PriorityLevel, UrgencyLevel


@dataclass
class IntentObject:
    """Universal Intent object passed to Planner and Reasoning engines."""
    goal: str
    action: str = "unknown"
    actor_role: str = "customer"
    actor_id: str = "user"
    category: IntentCategory | str = IntentCategory.UNKNOWN
    target_objects: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    priority: PriorityLevel | str = PriorityLevel.MEDIUM
    urgency: UrgencyLevel | str = UrgencyLevel.NORMAL
    confidence: float = 1.0
    missing_info: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    raw_text: str = ""
    intent_id: str = field(default_factory=lambda: f"intent_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "goal": self.goal,
            "action": self.action,
            "actor_role": self.actor_role,
            "actor_id": self.actor_id,
            "category": str(self.category.value if hasattr(self.category, "value") else self.category),
            "target_objects": self.target_objects,
            "constraints": self.constraints,
            "priority": str(self.priority.value if hasattr(self.priority, "value") else self.priority),
            "urgency": str(self.urgency.value if hasattr(self.urgency, "value") else self.urgency),
            "confidence": self.confidence,
            "missing_info": self.missing_info,
            "required_capabilities": self.required_capabilities,
            "raw_text": self.raw_text,
        }

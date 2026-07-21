"""B.O.S. Orchestrator Context v0.1

Execution container used during AI orchestration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from ..intent import IntentObject


@dataclass
class OrchestratorContext:
    """Context object encapsulating intent and engine state for orchestration."""
    intent: IntentObject
    engine_data: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "engine_data": self.engine_data,
            "options": self.options,
        }

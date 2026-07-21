"""B.O.S. Reasoning Result v0.1

Container object produced by Reasoning Engine containing insights and multi-step strategy.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReasoningResult:
    """Output produced by ReasoningEngine."""
    insights: List[str] = field(default_factory=list)
    recommended_capabilities: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    context_summary: Dict[str, Any] = field(default_factory=dict)
    multi_step_strategy: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insights": self.insights,
            "recommended_capabilities": self.recommended_capabilities,
            "risk_factors": self.risk_factors,
            "context_summary": self.context_summary,
            "multi_step_strategy": self.multi_step_strategy,
        }

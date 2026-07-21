"""B.O.S. Reasoning Engine v0.2

Primary Reasoning Engine facade synthesizing Business, Knowledge, Memory, and Capability reasoning.
"""

from typing import Any, Dict
from ..contracts import BusinessIntent, RuntimeContext
from ..intent import IntentObject
from .reasoning_result import ReasoningResult
from .business_reasoner import BusinessReasoner
from .knowledge_reasoner import KnowledgeReasoner
from .memory_reasoner import MemoryReasoner
from .capability_reasoner import CapabilityReasoner


class ReasoningEngine:
    """Synthesizes reasoning insights across business, knowledge, memory, and capability domains."""

    @classmethod
    def analyze_reasoning(cls, intent: IntentObject) -> ReasoningResult:
        biz_insights = BusinessReasoner.reason(intent)
        know_insights = KnowledgeReasoner.reason(intent)
        mem_insights = MemoryReasoner.reason(intent)
        recommended_caps = CapabilityReasoner.reason(intent)

        strategy = [
            "Observe request parameters and intent",
            "Evaluate safety and policy constraints",
            "Select capabilities and build execution graph",
            "Execute steps and verify response truth",
        ]

        return ReasoningResult(
            insights=biz_insights + know_insights + mem_insights,
            recommended_capabilities=recommended_caps,
            risk_factors=[f"Risk level: {intent.priority}"],
            context_summary={"action": intent.action, "actor": intent.actor_id},
            multi_step_strategy=strategy,
        )

    @classmethod
    def reason(cls, intent: Any, context: Any = None) -> ReasoningResult:
        """Backward-compatible entry point for Runtime Lifecycle Stage 4."""
        if not isinstance(intent, IntentObject):
            action_name = getattr(intent, "action", "unknown")
            intent_obj = IntentObject(
                goal=getattr(intent, "goal", ""),
                action=action_name,
                actor_role="owner" if context and getattr(context, "owner_preferences", None) else "customer",
                required_capabilities=[action_name] if action_name != "unknown" else ["messaging"],
            )
        else:
            intent_obj = intent

        return cls.analyze_reasoning(intent_obj)

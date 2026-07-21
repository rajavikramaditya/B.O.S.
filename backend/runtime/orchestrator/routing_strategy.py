"""B.O.S. Orchestrator Routing Strategy v0.1

Determines participating engines based on IntentObject attributes.
"""

from typing import List
from ..intent import IntentObject, IntentCategory, PriorityLevel


class RoutingStrategy:
    """Evaluates IntentObject to decide which cognitive and reasoning engines must participate."""

    @classmethod
    def determine_participating_engines(cls, intent: IntentObject) -> List[str]:
        engines = ["intent_engine", "reasoning_engine", "planner"]

        # If priority or risk requires decision engine
        if intent.priority in (PriorityLevel.HIGH, PriorityLevel.CRITICAL) or intent.action != "unknown":
            engines.append("decision_engine")

        # Policy engine always participates
        engines.append("policy_engine")

        # Check knowledge and memory needs
        if intent.category == IntentCategory.INQUIRY or "know" in intent.goal.lower():
            engines.append("knowledge_graph")

        if "history" in intent.goal.lower() or intent.actor_role == "customer":
            engines.append("workflow_memory")

        if intent.required_capabilities:
            engines.append("capability_graph")
            engines.append("capability_registry")

        if intent.actor_role == "owner":
            engines.append("business_graph")

        return engines

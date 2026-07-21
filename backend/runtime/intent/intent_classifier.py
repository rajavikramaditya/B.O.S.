"""B.O.S. Intent Classifier v0.1

Classifies intent categories and identifies required capabilities based on business actions.
"""

from typing import List, Tuple
from .intent_types import IntentCategory, PriorityLevel, UrgencyLevel


class IntentClassifier:
    """Classifies user requests into intent categories, priority, and required capabilities."""

    @staticmethod
    def classify(action: str, raw_text: str, role: str) -> Tuple[IntentCategory, List[str], PriorityLevel, UrgencyLevel]:
        text_lower = (raw_text or "").lower()

        # Determine Category
        category = IntentCategory.COMMAND
        if role == "customer":
            category = IntentCategory.INQUIRY
        elif text_lower in ("haan", "yes", "confirm", "kar do", "approve"):
            category = IntentCategory.APPROVAL_REPLY
        elif "schedule" in text_lower or "meeting" in text_lower or "workflow" in text_lower:
            category = IntentCategory.WORKFLOW_REQUEST

        # Determine Priority & Urgency
        priority = PriorityLevel.MEDIUM
        urgency = UrgencyLevel.NORMAL

        if any(w in text_lower for w in ("urgent", "immediately", "asap", "turant")):
            priority = PriorityLevel.HIGH
            urgency = UrgencyLevel.IMMEDIATE
        elif any(w in text_lower for w in ("baad me", "later", "deferred")):
            urgency = UrgencyLevel.DEFERRED

        # Resolve Capabilities
        required_caps: List[str] = []
        if action and action != "unknown":
            from ..registry import UniversalCapabilityRegistry

            cap = UniversalCapabilityRegistry.find_capability_for_action(action)
            if cap:
                required_caps.append(cap.name)
            else:
                required_caps.append(action)

        if not required_caps:
            required_caps = ["messaging"]

        return category, required_caps, priority, urgency

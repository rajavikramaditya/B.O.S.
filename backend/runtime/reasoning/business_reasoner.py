"""B.O.S. Business Reasoner v0.1

Performs business relationship and organizational goal reasoning.
"""

from typing import List
from ..intent import IntentObject


class BusinessReasoner:
    """Analyzes business impact and organizational context."""

    @classmethod
    def reason(cls, intent: IntentObject) -> List[str]:
        insights = []
        if intent.actor_role == "owner":
            insights.append("Owner priority command: require policy validation and high clarity.")
        elif intent.actor_role == "customer":
            insights.append("Customer request: prioritize helpfulness, clarity, and safety.")
        return insights

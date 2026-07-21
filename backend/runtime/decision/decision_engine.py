"""B.O.S. Decision Engine v0.1

Primary Runtime Decision Engine evaluating risk, business decisions, approval needs,
retries, fallbacks, and conflict resolution.
"""

from typing import Any, Dict
from ..intent import IntentObject
from .decision import DecisionResult
from .decision_rules import DecisionRules


class DecisionEngine:
    """Evaluates business intent and context to produce actionable reasoning decisions."""

    @classmethod
    def evaluate(
        cls,
        intent: IntentObject,
        context: Dict[str, Any] | None = None,
    ) -> DecisionResult:
        action = intent.action
        params = intent.constraints
        role = intent.actor_role

        risk_score, risk_level, approval_req = DecisionRules.evaluate_risk(action, params, role)

        rec_action = "execute"
        can_auto = True
        if approval_req:
            rec_action = "confirm"
            can_auto = False
        elif risk_level in ("HIGH", "CRITICAL"):
            rec_action = "escalate"
            can_auto = False

        # Priority resolution based on intent priority
        prio_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 5}
        priority_val = prio_map.get(str(intent.priority).upper(), 2)

        # Retry policy decision
        retry_decision = {
            "should_retry": risk_level not in ("CRITICAL",),
            "max_retries": 3 if risk_level == "LOW" else 1,
            "backoff_seconds": 1.0,
        }

        # Fallback decision
        fallback_decision = None
        if action == "generate_audio":
            fallback_decision = {"fallback_action": "prepare_capsule_audio", "reason": "audio generation fallback"}

        return DecisionResult(
            risk_score=risk_score,
            risk_level=risk_level,
            business_approval_required=approval_req,
            can_auto_execute=can_auto,
            recommended_action=rec_action,
            retry_decision=retry_decision,
            fallback_decision=fallback_decision,
            execution_priority=priority_val,
            notes=[f"Action evaluated: {action}, Risk level: {risk_level}"],
        )

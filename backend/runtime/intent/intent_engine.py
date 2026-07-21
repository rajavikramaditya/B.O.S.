"""B.O.S. Intent Engine v0.1

Primary Runtime Intent Engine analyzing requests to construct comprehensive IntentObjects.
"""

from typing import Any, Dict
from ..contracts import NormalizedRequest
from .intent import IntentObject
from .intent_types import IntentCategory, PriorityLevel, UrgencyLevel
from .intent_classifier import IntentClassifier


class IntentEngine:
    """Extracts goals, actors, target objects, constraints, priority, urgency, and capability requirements."""

    @classmethod
    def analyze(cls, request: NormalizedRequest) -> IntentObject:
        raw_text = request.message
        role = request.role

        action = "unknown"
        entities: Dict[str, Any] = {}
        confidence = 1.0

        if role == "owner":
            try:
                from services.brain.command_interpreter import interpret_owner_command

                interp_res = interpret_owner_command(raw_text)
                interp = interp_res[0] if isinstance(interp_res, tuple) and interp_res else (interp_res if isinstance(interp_res, dict) else {})
                if isinstance(interp, dict):
                    action = interp.get("action", "unknown")
                    entities = interp.get("slots", {}) or {}
                    confidence = float(interp.get("confidence", 1.0))
            except Exception:
                pass
        elif role == "customer":
            action = "chat"
            entities = {"sender_name": request.sender_name, "phone": request.phone}

        category, req_caps, priority, urgency = IntentClassifier.classify(action, raw_text, role)

        # Identify target objects
        target_objs = list(entities.keys()) if entities else []
        if action and action != "unknown":
            target_objs.append(action)

        return IntentObject(
            goal=raw_text,
            action=action,
            actor_role=role,
            actor_id=request.sender_name or "user",
            category=category,
            target_objects=target_objs,
            constraints=entities,
            priority=priority,
            urgency=urgency,
            confidence=confidence,
            missing_info=[],
            required_capabilities=req_caps,
            raw_text=raw_text,
        )

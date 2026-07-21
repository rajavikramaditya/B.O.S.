"""B.O.S. Understanding Engine v0.1

Stage 2 of Runtime Lifecycle: Interprets request to extract business intent and goal.
"""

from typing import Any, Dict
from .contracts import NormalizedRequest, BusinessIntent


class UnderstandingEngine:
    """Derives business intent and goals from normalized requests using AI reasoning."""

    @staticmethod
    def understand(request: NormalizedRequest) -> BusinessIntent:
        if request.role == "owner":
            from services.brain.command_interpreter import interpret_owner_command

            interp_res = interpret_owner_command(request.message)
            interp = interp_res[0] if isinstance(interp_res, tuple) and interp_res else (interp_res if isinstance(interp_res, dict) else {})
            if not isinstance(interp, dict):
                interp = {}
            return BusinessIntent(
                intent_type=interp.get("intent", "general_command"),
                action=interp.get("action", "unknown"),
                entities=interp.get("slots", {}) or {},
                goal=interp.get("goal", request.message),
                slots=interp.get("slots", {}) or {},
                confidence=float(interp.get("confidence", 1.0)),
            )

        return BusinessIntent(
            intent_type="customer_chat" if request.role == "customer" else "employee_stub",
            action="chat" if request.role == "customer" else "stub",
            entities={"sender_name": request.sender_name, "phone": request.phone},
            goal=request.message,
            slots={},
            confidence=1.0,
        )

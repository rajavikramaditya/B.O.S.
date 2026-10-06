"""B.O.S. Response Engine v1.0

Stage 11 of Runtime Lifecycle: Composes the final reply from verified facts only.
When steps ran, the reply is re-grounded on their real results so nothing is overstated.
"""

import json
from typing import Any, Dict, List

from .cognition import AI_UNAVAILABLE, RuntimeCognition
from .understanding import INTERNAL_ROLES
from .contracts import (
    BusinessIntent,
    ExecutionResult,
    NormalizedRequest,
    PolicyDecision,
    RuntimeContext,
    RuntimeResponse,
    VerificationReport,
)

SETUP_REPLY = (
    "I'm not connected to an AI model yet, so I can't think this through. "
    "Open Settings → AI and add a Claude or Gemini API key — it takes under a minute."
)

GROUNDING_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


class ResponseEngine:
    """Formats the final, truthful response for callers."""

    @staticmethod
    def generate_response(
        request: NormalizedRequest,
        verification: VerificationReport,
        execution_result: ExecutionResult,
        intent: BusinessIntent | None = None,
        policy: PolicyDecision | None = None,
        context: RuntimeContext | None = None,
    ) -> RuntimeResponse:
        intent = intent or BusinessIntent()
        pending = [ResponseEngine._step_view(s) for s in (policy.pending_steps if policy else [])]
        denied = policy.denied_steps if policy else []

        if not intent.understood_by and intent.error:
            reply = SETUP_REPLY if intent.error.startswith(AI_UNAVAILABLE) else (
                "I couldn't process that just now. Please try again in a moment."
            )
        elif not execution_result.step_results and not pending and not denied:
            reply = intent.reply_draft
        elif intent.understood_by == "explicit":
            reply = ResponseEngine._plain_summary(intent, ResponseEngine._facts(intent, execution_result, pending, denied))
        else:
            reply = ResponseEngine._grounded_reply(request, intent, execution_result, pending, denied, context)

        return RuntimeResponse(
            reply=reply,
            action_type=execution_result.action_type or "REPLY_ONLY",
            factual_packet=verification.factual_packet or execution_result.factual_packet or {},
            route="runtime",
            source="bos_runtime",
            role=request.role,
            trace={
                "request_id": request.request_id,
                "truth_level": verification.truth_level,
                "intent": intent.intent_type,
                "goal": intent.goal,
            },
        )

    @staticmethod
    def _step_view(step: Any) -> Dict[str, Any]:
        return {"step_id": step.step_id, "title": step.title, "capability": step.capability, "action": step.action, "risk": step.risk}

    @staticmethod
    def _grounded_reply(
        request: NormalizedRequest,
        intent: BusinessIntent,
        execution: ExecutionResult,
        pending: List[Dict[str, Any]],
        denied: List[Dict[str, Any]],
        context: RuntimeContext | None,
    ) -> str:
        facts = ResponseEngine._facts(intent, execution, pending, denied, internal=request.role in INTERNAL_ROLES)
        audience = "the business owner" if request.role == "owner" else ("an internal log" if request.role == "system" else "the person you are talking to")
        system = (
            "You finalize replies for B.O.S. Rewrite the draft reply so it matches the verified facts exactly. "
            "Say what was completed, what is waiting for approval and what failed — never claim anything beyond the facts. "
            "Remove any claim that an order, booking, payment, delivery or message is confirmed unless a completed fact "
            "shows exactly that; instead say what happens next (for example, that the team will confirm). "
            "For customers, never mention internal approvals, tools or errors; just say what will happen next in a natural way. "
            "Keep every price, quantity, date and name exactly as written in the draft — never change numbers. "
            f"Keep the draft's language ({intent.language or 'same as the draft'}), tone and forward-looking next step. "
            f"The reply is for {audience}."
        )
        data, _text, error = RuntimeCognition.think(
            system,
            [{"role": "user", "content": json.dumps(facts, ensure_ascii=False, default=str)[:12000]}],
            GROUNDING_SCHEMA,
            correlation_id=request.request_id,
            effort="low",
            max_tokens=2000,
        )
        if isinstance(data, dict) and data.get("reply"):
            return str(data["reply"])
        return ResponseEngine._plain_summary(intent, facts)

    @staticmethod
    def _facts(
        intent: BusinessIntent,
        execution: ExecutionResult,
        pending: List[Dict[str, Any]],
        denied: List[Dict[str, Any]],
        internal: bool = True,
    ) -> Dict[str, Any]:
        # Customer-facing replies are grounded on what happened, never on record contents
        # (a saved contact row carries staff notes, tags and stage).
        return {
            "draft_reply": intent.reply_draft,
            "completed": [
                {"title": r["title"], "result": r.get("data")} if internal else {"title": r["title"]}
                for r in execution.step_results
                if r["success"]
            ],
            "failed": [{"title": r["title"], "error": r.get("error")} for r in execution.step_results if not r["success"]],
            "awaiting_owner_approval": [p["title"] for p in pending],
            "not_allowed": denied,
        }

    @staticmethod
    def _plain_summary(intent: BusinessIntent, facts: Dict[str, Any]) -> str:
        lines = [intent.reply_draft] if intent.reply_draft and not facts["failed"] else []
        if facts["completed"]:
            lines.append("Done: " + "; ".join(c["title"] for c in facts["completed"]))
        if facts["awaiting_owner_approval"]:
            lines.append("Waiting for approval: " + "; ".join(facts["awaiting_owner_approval"]))
        if facts["failed"]:
            lines.append("Couldn't complete: " + "; ".join(f["title"] for f in facts["failed"]))
        return "\n".join(lines) or "Noted."

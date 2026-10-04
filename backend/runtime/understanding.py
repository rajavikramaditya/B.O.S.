"""B.O.S. Understanding Engine v1.0

Stage 3 of Runtime Lifecycle (ADR-008): Interprets the request with AI reasoning,
using the context loaded in Stage 2, and proposes what should happen next.

No keyword matching, no regex, no hardcoded intents: interpretation is delegated to
the `generate_text` capability with a structured output schema.
"""

import json
from typing import Any, Dict, List, Optional

from .cognition import RuntimeCognition
from .contracts import BusinessIntent, NormalizedRequest, RuntimeContext

COGNITION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_type": {"type": "string", "description": "Short snake_case label for what the actor wants."},
        "goal": {"type": "string", "description": "The underlying outcome the actor is trying to reach."},
        "summary": {"type": "string", "description": "One-line summary of the request."},
        "language": {"type": "string", "description": "Language/style the actor used, e.g. English, Hindi, Hinglish."},
        "confidence": {"type": "number"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string"},
                    "action": {"type": "string"},
                    "params_json": {"type": "string", "description": "JSON object string with the action parameters."},
                    "title": {"type": "string", "description": "Human-readable description of the step."},
                    "reason": {"type": "string", "description": "Why this step moves the business forward."},
                },
                "required": ["capability", "action", "params_json", "title", "reason"],
                "additionalProperties": False,
            },
        },
        "reply": {"type": "string", "description": "Message back to the actor. Empty for silent background events."},
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["title", "detail", "priority"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["intent_type", "goal", "summary", "language", "confidence", "entities", "steps", "reply", "insights"],
    "additionalProperties": False,
}

AUDIENCE = {
    "owner": "the business owner (your principal). Act like a trusted chief operating officer.",
    "employee": "a team member of the business. Help them get work done within their role.",
    "customer": "a customer or prospect of the business. You represent the business to them.",
    "system": "the platform itself (a scheduled review or an external event). No human is waiting for a chat reply.",
}

INTERNAL_ROLES = ("owner", "employee", "system")

OPERATING_PRINCIPLES = """\
How you operate (B.O.S. principles):
1. Lead, don't wait. Anticipate what the person needs next and guide them there. Every reply should move
   things forward: answer, then propose the clear next step. Ask at most one focused question at a time.
2. With customers: understand their need, recommend the right offering, and steer toward an outcome
   (purchase, booking, resolution). Capture useful details (name, contact, need) naturally — never pushy.
   When someone shows real interest, save or update them as a contact and plan a follow-up task.
3. With the owner: run the business with them. Do the work through steps, then report briefly.
   Surface risks, opportunities and anything waiting on their decision.
4. Truth first. Actions happen ONLY through planned steps. Never claim something was sent, booked, saved
   or changed — the platform verifies steps and reports real results afterwards. Never invent prices,
   policies, stock or availability that are not in the business profile; offer to confirm instead and
   plan a task for the owner. Saving a contact is not a booking: never say an order is booked or
   confirmed unless a step actually does that.
5. Reply in the same language and script as the person's latest message — Hinglish gets Hinglish,
   Hindi gets Hindi, English gets English. Be warm, concise and natural.
6. When actor_profile has an id, that person is already a contact: update them with that id
   instead of creating a new contact.

Planning rules:
- Use only capabilities and actions from the catalog. params_json must be a JSON object string with that
  action's parameters. Plan no steps when a reply alone is enough.
- Refer to the output of an earlier step with "{{steps.N.<path>}}" (N starts at 1), e.g. a contact id
  created by step 1: "{{steps.1.contact.id}}".
- Each step's risk is declared in the catalog. External or sensitive steps may wait for owner approval;
  plan them anyway when they are the right move, and phrase the reply so it stays true either way.
- insights: notable observations for the owner (empty unless genuinely useful)."""


class UnderstandingEngine:
    """Derives business intent, goal and a proposed plan using AI reasoning."""

    @staticmethod
    def understand(request: NormalizedRequest, context: Optional[RuntimeContext] = None) -> BusinessIntent:
        context = context or RuntimeContext()
        preplanned = request.raw_payload.get("plan") if isinstance(request.raw_payload, dict) else None
        if isinstance(preplanned, list):
            return UnderstandingEngine._from_explicit_plan(request, preplanned)

        system = UnderstandingEngine._system_prompt(request, context)
        messages = UnderstandingEngine._messages(request, context)
        data, _text, error = RuntimeCognition.think(system, messages, COGNITION_SCHEMA, correlation_id=request.request_id)

        if not isinstance(data, dict):
            return BusinessIntent(
                intent_type="unavailable",
                action="none",
                goal=request.message,
                confidence=0.0,
                error=error or "AI reasoning returned no result.",
            )

        entities = {
            str(e.get("key")): e.get("value")
            for e in data.get("entities") or []
            if isinstance(e, dict) and e.get("key")
        }
        steps = [
            {
                "capability": str(s.get("capability") or ""),
                "action": str(s.get("action") or ""),
                "params": RuntimeCognition.parse_params(s.get("params_json")),
                "title": str(s.get("title") or ""),
                "reason": str(s.get("reason") or ""),
            }
            for s in data.get("steps") or []
            if isinstance(s, dict)
        ]
        return BusinessIntent(
            intent_type=str(data.get("intent_type") or "conversation"),
            action=steps[0]["action"] if steps else "reply",
            entities=entities,
            goal=str(data.get("goal") or request.message),
            slots={},
            confidence=float(data.get("confidence") or 0.0),
            summary=str(data.get("summary") or ""),
            language=str(data.get("language") or ""),
            proposed_steps=steps,
            reply_draft=str(data.get("reply") or ""),
            insights=[i for i in data.get("insights") or [] if isinstance(i, dict)],
            understood_by="ai",
        )

    @staticmethod
    def _from_explicit_plan(request: NormalizedRequest, plan: List[Dict[str, Any]]) -> BusinessIntent:
        """Integrations and the dashboard may submit an explicit plan; it still passes Policy and Verification."""
        steps = [
            {
                "capability": str(s.get("capability") or ""),
                "action": str(s.get("action") or ""),
                "params": RuntimeCognition.parse_params(s.get("params")),
                "title": str(s.get("title") or f"{s.get('capability')}.{s.get('action')}"),
                "reason": str(s.get("reason") or "Requested explicitly."),
            }
            for s in plan
            if isinstance(s, dict)
        ]
        return BusinessIntent(
            intent_type="explicit_plan",
            action=steps[0]["action"] if steps else "none",
            goal=request.message or "Run the submitted plan",
            confidence=1.0,
            summary=request.message,
            proposed_steps=steps,
            understood_by="explicit",
        )

    @staticmethod
    def _system_prompt(request: NormalizedRequest, context: RuntimeContext) -> str:
        profile = context.business_profile or {}
        name = profile.get("assistant_name") or "the assistant"
        business = profile.get("name") or "this business"
        catalog = json.dumps(context.capability_catalog, ensure_ascii=False)
        return (
            f"You are {name}, the AI operator of {business}, running on B.O.S. (Business Operating System).\n\n"
            f"Business profile:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
            f"{OPERATING_PRINCIPLES}\n\n"
            f"Capability catalog:\n{catalog}"
        )

    @staticmethod
    def _messages(request: NormalizedRequest, context: RuntimeContext) -> List[Dict[str, str]]:
        history = [
            {"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")}
            for m in context.conversation_history
        ]
        situation = {
            "you_are_talking_to": AUDIENCE.get(request.role, AUDIENCE["customer"]),
            "channel": request.channel,
            "sender_name": request.sender_name,
            "actor_profile": context.actor_profile,
            "autopilot_mode": context.autopilot_mode,
        }
        if request.role in INTERNAL_ROLES:
            # Customers never see internal records (other customers, tasks, approvals).
            situation["business_snapshot"] = context.business_snapshot
        event = request.raw_payload.get("event") if isinstance(request.raw_payload, dict) else None
        if event:
            situation["event"] = event
        current = f"[situation]\n{json.dumps(situation, ensure_ascii=False, default=str)}\n[/situation]\n\n{request.message}"
        return history + [{"role": "user", "content": current}]

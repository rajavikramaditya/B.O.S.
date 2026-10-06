"""B.O.S. Public API v1

Stable, API-key protected endpoints for websites, apps and automation platforms.
Everything still flows through the Runtime, so Policy and Verification always apply.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gateway.runtime_gateway import RuntimeGateway
from integrations.api_keys import grants_for_scopes, key_conversation_id
from runtime.cognition import RuntimeCognition
from workspace.records import ContactRepository, TaskRepository

from ..security import Principal, require_scope

router = APIRouter(prefix="/v1", tags=["Public API v1"])


class ContactRef(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    external_id: str = ""


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(default=None, description="Reuse to continue a conversation.")
    channel: str = Field(default="api", description="Where the customer is (web, app, kiosk, ...).")
    contact: Optional[ContactRef] = None


class PlanStep(BaseModel):
    capability: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    title: str = ""
    reason: str = ""


class ActionsIn(BaseModel):
    plan: List[PlanStep] = Field(min_length=1, max_length=8)
    note: str = ""


class EventIn(BaseModel):
    type: str = Field(min_length=1, max_length=120, description="e.g. order.created, form.submitted")
    data: Dict[str, Any] = Field(default_factory=dict)


class ContactIn(ContactRef):
    stage: str = "lead"
    notes: str = ""
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


def _public(result: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("reply", "conversation_id", "workflow_status", "truth_level", "intent", "executed_steps", "approvals", "denied_steps")
    return {k: result.get(k) for k in keys}


@router.post("/messages", summary="Send a customer message and get B.O.S.'s reply")
def post_message(body: MessageIn, principal: Principal = Depends(require_scope("runtime"))) -> Dict[str, Any]:
    actor_ref = ""
    if body.contact and (body.contact.external_id or body.contact.phone or body.contact.email):
        actor_ref = RuntimeGateway.identify_contact(
            channel=body.channel,
            external_id=body.contact.external_id or body.contact.phone or body.contact.email,
            name=body.contact.name,
            phone=body.contact.phone,
            email=body.contact.email,
        )
    result = RuntimeGateway.submit(
        role="customer",
        message=body.message,
        channel=body.channel,
        conversation_id=key_conversation_id(principal.id, body.conversation_id, body.channel),
        sender_name=(body.contact.name if body.contact else "") or "Customer",
        actor_ref=actor_ref,
        source=f"api:{principal.name}",
    )
    return _public(result)


@router.post("/actions", summary="Run an explicit plan of capability actions (staff-level)")
def post_actions(body: ActionsIn, principal: Principal = Depends(require_scope("operator"))) -> Dict[str, Any]:
    # Keys act as staff, never as the platform: external or sensitive steps still wait for the owner.
    result = RuntimeGateway.submit(
        role="employee",
        message=body.note or "Run actions requested through the API",
        channel="api",
        conversation_id=key_conversation_id(principal.id, "actions"),
        sender_name=principal.name,
        raw_payload={"plan": [s.model_dump() for s in body.plan]},
        grants=grants_for_scopes(principal.scopes),
        source=f"api:{principal.name}",
    )
    return _public(result)


@router.post("/events", summary="Tell B.O.S. something happened; it decides what to do")
def post_event(body: EventIn, principal: Principal = Depends(require_scope("events"))) -> Dict[str, Any]:
    result = RuntimeGateway.submit(
        role="employee",  # an integration is staff-level, never the platform itself
        message=f"An external event arrived from '{principal.name}': {body.type}. Decide whether and how the business should act.",
        channel="events",
        conversation_id=key_conversation_id(principal.id, body.type, "events"),
        sender_name=principal.name,
        raw_payload={"event": {"type": body.type, "data": body.data}},
        grants=grants_for_scopes(principal.scopes),
        source=f"event:{body.type}",
    )
    return _public(result)


@router.get("/capabilities", summary="What B.O.S. can do (capabilities, actions, risk levels)")
def capabilities(principal: Principal = Depends(require_scope("runtime"))) -> List[Dict[str, Any]]:
    return RuntimeCognition.capability_catalog()


@router.get("/contacts")
def list_contacts(search: str = "", stage: str = "", principal: Principal = Depends(require_scope("records:read"))) -> List[Dict[str, Any]]:
    return ContactRepository.list(search, stage, limit=200)


@router.post("/contacts")
def save_contact(body: ContactIn, principal: Principal = Depends(require_scope("records:write"))) -> Dict[str, Any]:
    result = RuntimeGateway.submit(
        role="employee",
        message="Save a contact submitted through the API",
        channel="api",
        conversation_id=key_conversation_id(principal.id, "actions"),
        sender_name=principal.name,
        raw_payload={"plan": [{"capability": "contacts", "action": "upsert_contact", "params": body.model_dump(), "title": "Save contact"}]},
        grants=grants_for_scopes(principal.scopes),
        source=f"api:{principal.name}",
    )
    return _public(result)


@router.get("/tasks")
def list_tasks(status_filter: str = "open", principal: Principal = Depends(require_scope("records:read"))) -> List[Dict[str, Any]]:
    return TaskRepository.list(status_filter if status_filter != "all" else "", limit=200)

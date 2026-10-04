"""B.O.S. Workspace Routes v1.0

Owner dashboard: overview, business profile, Autopilot, chat, conversations,
approvals, contacts and tasks. Every action goes through the Runtime Gateway.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from autopilot.engine import AutopilotEngine
from capabilities.base.capability_context import CapabilityContext
from capabilities.resolver import CapabilityResolver
from gateway.runtime_gateway import RuntimeGateway
from workspace.activity import ActivityLog
from workspace.approvals import ApprovalRepository
from workspace.records import ContactRepository, TaskRepository
from workspace.settings_store import AUTOPILOT, AUTOPILOT_MODES, BUSINESS_PROFILE, SettingsStore

from ..security import require_owner
from .system import setup_checklist

router = APIRouter(prefix="/api", tags=["Workspace"], dependencies=[Depends(require_owner)])


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    offerings: Optional[str] = None
    target_customers: Optional[str] = None
    goals: Optional[List[str]] = None
    tone: Optional[str] = None
    languages: Optional[List[str]] = None
    assistant_name: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None
    location: Optional[str] = None


class AutopilotUpdate(BaseModel):
    mode: Optional[str] = None
    briefing_enabled: Optional[bool] = None


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: Optional[str] = None
    as_customer: bool = False
    customer_name: Optional[str] = None


def _memory(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    result = CapabilityResolver.execute("conversation_memory", action, params, CapabilityContext(module_id="dashboard"))
    if not result.success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, result.error or "Not found.")
    return result.data or {}


@router.get("/dashboard")
def dashboard() -> Dict[str, Any]:
    conversations = _memory("list_conversations", {"limit": 6})
    return {
        "profile": SettingsStore.get(BUSINESS_PROFILE),
        "autopilot": {**SettingsStore.get(AUTOPILOT), "latest": AutopilotEngine.latest()},
        "stats": {
            "contacts": ContactRepository.stats(),
            "tasks": TaskRepository.stats(),
            "pending_approvals": ApprovalRepository.pending_count(),
            "conversations": conversations.get("total", 0),
        },
        "approvals": ApprovalRepository.list("pending", limit=5),
        "tasks": TaskRepository.list("open", limit=6),
        "conversations": [c for c in conversations.get("conversations", []) if c["actor"] in ("customer", "employee")][:5],
        "activity": ActivityLog.recent(15),
        "setup": setup_checklist(),
    }


@router.get("/business/profile")
def get_profile() -> Dict[str, Any]:
    return SettingsStore.get(BUSINESS_PROFILE)


@router.put("/business/profile")
def update_profile(body: ProfileUpdate) -> Dict[str, Any]:
    profile = SettingsStore.update(BUSINESS_PROFILE, body.model_dump(exclude_none=True))
    ActivityLog.record("profile.updated", "Business profile updated")
    return profile


@router.get("/autopilot")
def autopilot_overview() -> Dict[str, Any]:
    return {"settings": SettingsStore.get(AUTOPILOT), "modes": list(AUTOPILOT_MODES), "latest": AutopilotEngine.latest(), "history": AutopilotEngine.history(10)}


@router.put("/autopilot")
def update_autopilot(body: AutopilotUpdate) -> Dict[str, Any]:
    if body.mode is not None and body.mode not in AUTOPILOT_MODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"mode must be one of {AUTOPILOT_MODES}")
    settings = SettingsStore.update(AUTOPILOT, body.model_dump(exclude_none=True))
    ActivityLog.record("autopilot.mode", f"Autopilot mode set to {settings['mode']}")
    return settings


@router.post("/autopilot/run")
def run_autopilot() -> Dict[str, Any]:
    return AutopilotEngine.run(trigger="manual")


@router.post("/chat")
def chat(body: ChatMessage) -> Dict[str, Any]:
    """Talk to B.O.S. as the owner, or preview exactly what a customer would experience."""
    if body.as_customer:
        conversation_id = body.conversation_id or f"preview:{uuid.uuid4().hex[:10]}"
        result = RuntimeGateway.submit(
            role="customer",
            message=body.message,
            channel="preview",
            conversation_id=conversation_id,
            sender_name=body.customer_name or "Preview customer",
            source="preview",
        )
    else:
        conversation_id = body.conversation_id or f"owner:{uuid.uuid4().hex[:10]}"
        result = RuntimeGateway.submit(
            role="owner", message=body.message, channel="dashboard", conversation_id=conversation_id, sender_name="Owner"
        )
    return result


@router.get("/conversations")
def conversations(actor: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    return _memory("list_conversations", {"limit": limit, "actor": actor or ""})


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str) -> Dict[str, Any]:
    meta = _memory("get_conversation", {"conversation_id": conversation_id})
    history = _memory("history", {"conversation_id": conversation_id, "limit": 200})
    return {"conversation": meta.get("conversation"), "messages": history.get("messages", [])}


@router.get("/approvals")
def approvals(status_filter: str = "pending") -> List[Dict[str, Any]]:
    return ApprovalRepository.list(status_filter if status_filter != "all" else "", limit=100)


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str) -> Dict[str, Any]:
    return RuntimeGateway.approve(approval_id)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str) -> Dict[str, Any]:
    return RuntimeGateway.reject(approval_id)


@router.get("/contacts")
def contacts(search: str = "", stage: str = "") -> List[Dict[str, Any]]:
    return ContactRepository.list(search, stage, limit=200)


@router.get("/tasks")
def tasks(status_filter: str = "open") -> List[Dict[str, Any]]:
    return TaskRepository.list(status_filter if status_filter != "all" else "", limit=200)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str) -> Dict[str, Any]:
    """The owner's click is the approval, so the step runs preapproved — still through the Runtime."""
    result = RuntimeGateway.submit(
        role="owner",
        message="Mark task as done",
        channel="dashboard",
        conversation_id="dashboard:actions",
        raw_payload={"plan": [{"capability": "tasks", "action": "complete_task", "params": {"task_id": task_id}, "title": "Complete task"}]},
        source="dashboard",
        preapproved=True,
    )
    steps = result.get("executed_steps") or []
    if not steps or not steps[0].get("success"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, (steps[0].get("error") if steps else None) or "Task not found.")
    return steps[0]["data"].get("task", {})

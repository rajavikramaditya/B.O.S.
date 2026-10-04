"""B.O.S. Workspace Models v1.0

Generic, industry-neutral business tables. Industry specifics belong in
contact/task `attributes` or in installable business modules.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import WorkspaceBase


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Owner(WorkspaceBase):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Setting(WorkspaceBase):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, default=dict)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time, onupdate=time.time)


class Contact(WorkspaceBase):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("con"))
    name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(60), default="", index=True)
    email: Mapped[str] = mapped_column(String(200), default="", index=True)
    channel: Mapped[str] = mapped_column(String(40), default="")
    external_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    stage: Mapped[str] = mapped_column(String(40), default="lead")
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time, onupdate=time.time)
    last_interaction_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Task(WorkspaceBase):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tsk"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    due_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), default="owner")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    completed_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Approval(WorkspaceBase):
    """A step the Runtime planned but policy held for a human decision."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("apr"))
    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text, default="")
    capability: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    risk: Mapped[str] = mapped_column(String(20), default="external")
    source: Mapped[str] = mapped_column(String(40), default="runtime")
    conversation_id: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    decided_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Activity(WorkspaceBase):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class ApiKey(WorkspaceBase):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("key"))
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(24), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    scopes: Mapped[List[str]] = mapped_column(JSON, default=list)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    last_used_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class WebhookSubscription(WorkspaceBase):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("whk"))
    url: Mapped[str] = mapped_column(String(1000))
    events: Mapped[List[str]] = mapped_column(JSON, default=list)
    secret_encrypted: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class WebhookDelivery(WorkspaceBase):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[str] = mapped_column(String(40), index=True)
    event: Mapped[str] = mapped_column(String(120))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    attempted_at: Mapped[float] = mapped_column(Float, default=time.time)


class Connection(WorkspaceBase):
    """Credentials and state for one connected integration."""

    __tablename__ = "connections"

    connector_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="connected")
    config_encrypted: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    connected_at: Mapped[float] = mapped_column(Float, default=time.time)


class AutopilotRun(WorkspaceBase):
    __tablename__ = "autopilot_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("run"))
    trigger: Mapped[str] = mapped_column(String(40), default="schedule")
    status: Mapped[str] = mapped_column(String(20), default="running")
    summary: Mapped[str] = mapped_column(Text, default="")
    insights: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    executed: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    pending_approvals: Mapped[List[str]] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    finished_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

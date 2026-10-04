"""B.O.S. System Routes v1.0

Health, first-run setup and owner sign-in.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from bootstrap.platform import VERSION, Platform
from integrations.connections import ConnectionStore
from workspace.activity import ActivityLog
from workspace.database import WorkspaceDatabase
from workspace.models import Owner
from workspace.settings_store import BUSINESS_PROFILE, SettingsStore

from ..rate_limit import auth_limiter
from ..security import Principal, hash_password, issue_session, require_owner, verify_password

router = APIRouter(prefix="/api", tags=["System"])


class OwnerSetup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class Login(BaseModel):
    email: EmailStr
    password: str


def setup_checklist() -> Dict[str, Any]:
    profile = SettingsStore.get(BUSINESS_PROFILE)
    channels = [c for c in ("telegram", "whatsapp", "email") if ConnectionStore.is_connected(c)]
    steps = [
        {"id": "owner", "title": "Create your owner account", "done": Platform.has_owner()},
        {"id": "ai", "title": "Connect an AI model", "done": Platform.ai_status()["configured"]},
        {"id": "profile", "title": "Describe your business", "done": bool(profile.get("name") and profile.get("description"))},
        {"id": "channel", "title": "Connect a customer channel", "done": bool(channels)},
    ]
    return {"steps": steps, "complete": all(s["done"] for s in steps), "connected_channels": channels}


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": VERSION, "ai": Platform.ai_status()["configured"]}


@router.get("/setup/status")
def setup_status() -> Dict[str, Any]:
    return {"owner_exists": Platform.has_owner(), "ai": Platform.ai_status(), **setup_checklist()}


@router.post("/setup/owner", dependencies=[Depends(auth_limiter)])
def create_owner(body: OwnerSetup) -> Dict[str, Any]:
    with WorkspaceDatabase.session() as db:
        if db.scalars(select(Owner).limit(1)).first() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Owner account already exists. Please sign in.")
        owner = Owner(name=body.name.strip(), email=body.email.lower(), password_hash=hash_password(body.password))
        db.add(owner)
        db.flush()
        owner_id, name = owner.id, owner.name
    ActivityLog.record("setup.owner", f"{name} created the workspace")
    return {"token": issue_session(owner_id), "owner": {"id": owner_id, "name": name, "email": body.email.lower()}}


@router.post("/auth/login", dependencies=[Depends(auth_limiter)])
def login(body: Login) -> Dict[str, Any]:
    with WorkspaceDatabase.session() as db:
        owner = db.scalars(select(Owner).where(Owner.email == body.email.lower())).first()
        if owner is None or not verify_password(body.password, owner.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
        return {"token": issue_session(owner.id), "owner": {"id": owner.id, "name": owner.name, "email": owner.email}}


@router.get("/auth/me")
def me(principal: Principal = Depends(require_owner)) -> Dict[str, Any]:
    with WorkspaceDatabase.session() as db:
        owner = db.get(Owner, principal.id)
        return {"id": owner.id, "name": owner.name, "email": owner.email}

"""B.O.S. Business Records Repository v1.0

Contacts (customers, leads, partners) and tasks (follow-ups, to-dos).
Accessed by the `workspace_records` provider and by read-only dashboard APIs.
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select

from .database import WorkspaceDatabase
from .models import Contact, Task

CONTACT_FIELDS = ("name", "phone", "email", "channel", "external_id", "stage", "tags", "notes", "attributes")


def contact_to_dict(c: Contact) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "channel": c.channel,
        "external_id": c.external_id,
        "stage": c.stage,
        "tags": c.tags or [],
        "notes": c.notes,
        "attributes": c.attributes or {},
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "last_interaction_at": c.last_interaction_at,
    }


def task_to_dict(t: Task) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "due_at": t.due_at,
        "contact_id": t.contact_id,
        "created_by": t.created_by,
        "created_at": t.created_at,
        "completed_at": t.completed_at,
    }


class ContactRepository:
    @staticmethod
    def _find(db, data: Dict[str, Any], match_on: tuple = ("external_id", "phone", "email")) -> Optional[Contact]:
        if data.get("id"):
            found = db.get(Contact, data["id"])
            if found:
                return found
        clauses = []
        if data.get("external_id") and "external_id" in match_on:
            clauses.append(Contact.external_id == str(data["external_id"]))
        if data.get("phone") and "phone" in match_on:
            clauses.append(Contact.phone == str(data["phone"]))
        if data.get("email") and "email" in match_on:
            clauses.append(Contact.email == str(data["email"]).lower())
        if not clauses:
            return None
        return db.scalars(select(Contact).where(or_(*clauses)).limit(1)).first()

    @staticmethod
    def upsert(data: Dict[str, Any], match_on: tuple = ("external_id", "phone", "email")) -> Dict[str, Any]:
        """Create or update a contact. Channel identities pass match_on=("external_id",) so an
        unverified phone/email can never attach one person to another person's record."""
        clean = {k: v for k, v in data.items() if k in CONTACT_FIELDS and v not in (None, "")}
        if "email" in clean:
            clean["email"] = str(clean["email"]).lower()
        with WorkspaceDatabase.session() as db:
            contact = ContactRepository._find(db, data, match_on)
            created = contact is None
            if created:
                contact = Contact()
                db.add(contact)
            for key, value in clean.items():
                if key == "attributes" and isinstance(value, dict):
                    contact.attributes = {**(contact.attributes or {}), **value}
                elif key == "tags" and isinstance(value, list):
                    contact.tags = sorted(set((contact.tags or []) + [str(t) for t in value]))
                elif key == "notes" and contact.notes and not created:
                    contact.notes = f"{contact.notes}\n{value}"
                else:
                    setattr(contact, key, value)
            contact.last_interaction_at = time.time()
            db.flush()
            out = contact_to_dict(contact)
            out["created"] = created
            return out

    @staticmethod
    def get(contact_id: str) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            c = db.get(Contact, contact_id)
            return contact_to_dict(c) if c else None

    @staticmethod
    def find(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            c = ContactRepository._find(db, data)
            return contact_to_dict(c) if c else None

    @staticmethod
    def list(search: str = "", stage: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            q = select(Contact)
            if stage:
                q = q.where(Contact.stage == stage)
            if search:
                like = f"%{search}%"
                q = q.where(or_(Contact.name.ilike(like), Contact.phone.ilike(like), Contact.email.ilike(like)))
            q = q.order_by(Contact.updated_at.desc()).limit(limit)
            return [contact_to_dict(c) for c in db.scalars(q).all()]

    @staticmethod
    def stats() -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            rows = db.execute(select(Contact.stage, func.count()).group_by(Contact.stage)).all()
            by_stage = {stage: count for stage, count in rows}
            week_ago = time.time() - 7 * 86400
            new_week = db.scalar(select(func.count()).select_from(Contact).where(Contact.created_at >= week_ago)) or 0
            return {"total": sum(by_stage.values()), "by_stage": by_stage, "new_this_week": new_week}


class TaskRepository:
    @staticmethod
    def create(data: Dict[str, Any]) -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            task = Task(
                title=str(data.get("title") or "Follow up")[:300],
                description=str(data.get("description") or ""),
                due_at=_as_timestamp(data.get("due_at")),
                contact_id=data.get("contact_id"),
                created_by=str(data.get("created_by") or "runtime"),
            )
            db.add(task)
            db.flush()
            return task_to_dict(task)

    @staticmethod
    def complete(task_id: str) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            task = db.get(Task, task_id)
            if not task:
                return None
            task.status = "done"
            task.completed_at = time.time()
            return task_to_dict(task)

    @staticmethod
    def list(status: str = "open", limit: int = 100) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            q = select(Task)
            if status:
                q = q.where(Task.status == status)
            q = q.order_by(Task.due_at.is_(None), Task.due_at.asc(), Task.created_at.desc()).limit(limit)
            return [task_to_dict(t) for t in db.scalars(q).all()]

    @staticmethod
    def stats() -> Dict[str, Any]:
        now = time.time()
        with WorkspaceDatabase.session() as db:
            open_count = db.scalar(select(func.count()).select_from(Task).where(Task.status == "open")) or 0
            overdue = db.scalar(
                select(func.count()).select_from(Task).where(Task.status == "open", Task.due_at.is_not(None), Task.due_at < now)
            ) or 0
            done_week = db.scalar(
                select(func.count()).select_from(Task).where(Task.status == "done", Task.completed_at >= now - 7 * 86400)
            ) or 0
            return {"open": open_count, "overdue": overdue, "done_this_week": done_week}


def _as_timestamp(value: Any) -> Optional[float]:
    """Accept epoch seconds or ISO-8601 strings (protocol parsing, not language parsing)."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None

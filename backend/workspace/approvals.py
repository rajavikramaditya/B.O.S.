"""B.O.S. Approval Repository v1.0

Stores plan steps that policy held for a human decision.
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from .database import WorkspaceDatabase
from .models import Approval


def approval_to_dict(a: Approval) -> Dict[str, Any]:
    return {
        "id": a.id,
        "title": a.title,
        "rationale": a.rationale,
        "capability": a.capability,
        "action": a.action,
        "params": a.params or {},
        "risk": a.risk,
        "source": a.source,
        "conversation_id": a.conversation_id,
        "status": a.status,
        "result": a.result or {},
        "created_at": a.created_at,
        "decided_at": a.decided_at,
    }


class ApprovalRepository:
    @staticmethod
    def create(step: Dict[str, Any], source: str, conversation_id: str = "") -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            item = Approval(
                title=str(step.get("title") or f"{step.get('capability')}.{step.get('action')}")[:300],
                rationale=str(step.get("reason") or ""),
                capability=str(step.get("capability")),
                action=str(step.get("action")),
                params=step.get("params") or {},
                risk=str(step.get("risk") or "external"),
                source=source,
                conversation_id=conversation_id,
            )
            db.add(item)
            db.flush()
            return approval_to_dict(item)

    @staticmethod
    def get(approval_id: str) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            a = db.get(Approval, approval_id)
            return approval_to_dict(a) if a else None

    @staticmethod
    def list(status: str = "pending", limit: int = 100) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            q = select(Approval)
            if status:
                q = q.where(Approval.status == status)
            q = q.order_by(Approval.created_at.desc()).limit(limit)
            return [approval_to_dict(a) for a in db.scalars(q).all()]

    @staticmethod
    def set_status(approval_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            a = db.get(Approval, approval_id)
            if not a:
                return None
            a.status = status
            a.decided_at = time.time()
            if result is not None:
                a.result = result
            return approval_to_dict(a)

    @staticmethod
    def claim_pending(approval_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Atomically move a pending approval to `status`; None if it was not pending."""
        with WorkspaceDatabase.session() as db:
            a = db.get(Approval, approval_id)
            if not a or a.status != "pending":
                return None
            a.status = status
            a.decided_at = time.time()
            return approval_to_dict(a)

    @staticmethod
    def pending_count() -> int:
        with WorkspaceDatabase.session() as db:
            return db.scalar(select(func.count()).select_from(Approval).where(Approval.status == "pending")) or 0

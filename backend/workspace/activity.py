"""B.O.S. Activity Log v1.0

Human-readable timeline of what the platform did and why.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .database import WorkspaceDatabase
from .models import Activity


class ActivityLog:
    """Append-only activity feed shown on the dashboard."""

    @staticmethod
    def record(kind: str, title: str, detail: Optional[Dict[str, Any]] = None) -> None:
        with WorkspaceDatabase.session() as db:
            db.add(Activity(kind=kind, title=title[:300], detail=detail or {}))

    @staticmethod
    def recent(limit: int = 30) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            rows = db.scalars(select(Activity).order_by(Activity.id.desc()).limit(limit)).all()
            return [
                {"id": r.id, "kind": r.kind, "title": r.title, "detail": r.detail, "created_at": r.created_at}
                for r in rows
            ]

"""B.O.S. Connection Store v1.0

Encrypted credentials and state for connected integrations.
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from workspace.database import WorkspaceDatabase
from workspace.models import Connection
from workspace.vault import WorkspaceVault


class ConnectionStore:
    @staticmethod
    def save(connector_id: str, credentials: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            if row is None:
                row = Connection(connector_id=connector_id)
                db.add(row)
            row.status = "connected"
            row.config_encrypted = WorkspaceVault.encrypt_json(credentials)
            row.meta = meta or row.meta or {}
            row.connected_at = time.time()

    @staticmethod
    def credentials(connector_id: str) -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            if row is None or row.status != "connected":
                return {}
            return WorkspaceVault.decrypt_json(row.config_encrypted)

    @staticmethod
    def meta(connector_id: str) -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            return dict(row.meta or {}) if row else {}

    @staticmethod
    def update_meta(connector_id: str, values: Dict[str, Any]) -> None:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            if row:
                row.meta = {**(row.meta or {}), **values}

    @staticmethod
    def remove(connector_id: str) -> bool:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            if row is None:
                return False
            db.delete(row)
            return True

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            rows = db.scalars(select(Connection)).all()
            return [
                {"connector_id": r.connector_id, "status": r.status, "meta": r.meta or {}, "connected_at": r.connected_at}
                for r in rows
            ]

    @staticmethod
    def is_connected(connector_id: str) -> bool:
        with WorkspaceDatabase.session() as db:
            row = db.get(Connection, connector_id)
            return bool(row and row.status == "connected")

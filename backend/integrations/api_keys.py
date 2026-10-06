"""B.O.S. API Keys v1.0

Scoped keys for the public REST API and MCP server. Only a SHA-256 hash is stored.
"""

import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from workspace.database import WorkspaceDatabase
from workspace.models import ApiKey

# runtime       — send customer messages (/v1/messages)
# operator      — act as staff: explicit actions (/v1/actions) and the MCP server
# records:read  — read contacts, tasks and approvals
# records:write — save contacts
# events        — report external events (/v1/events)
SCOPES = ("runtime", "operator", "records:read", "records:write", "events")
KEY_PREFIX = "bos_live_"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def key_to_dict(k: ApiKey) -> Dict[str, Any]:
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "scopes": k.scopes or [],
        "revoked": k.revoked,
        "created_at": k.created_at,
        "last_used_at": k.last_used_at,
    }


class ApiKeyService:
    @staticmethod
    def create(name: str, scopes: List[str]) -> Dict[str, Any]:
        raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
        valid = [s for s in scopes if s in SCOPES] or list(SCOPES)
        with WorkspaceDatabase.session() as db:
            key = ApiKey(name=name or "API key", prefix=raw[:16], key_hash=_hash(raw), scopes=valid)
            db.add(key)
            db.flush()
            out = key_to_dict(key)
        out["key"] = raw  # shown once
        return out

    @staticmethod
    def verify(raw: str, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the key when valid (and granted `scope`, if given)."""
        if not raw or not raw.startswith(KEY_PREFIX):
            return None
        with WorkspaceDatabase.session() as db:
            key = db.scalars(select(ApiKey).where(ApiKey.key_hash == _hash(raw))).first()
            if key is None or key.revoked or (scope is not None and scope not in (key.scopes or [])):
                return None
            key.last_used_at = time.time()
            return key_to_dict(key)

    @staticmethod
    def list() -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            return [key_to_dict(k) for k in db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()]

    @staticmethod
    def revoke(key_id: str) -> bool:
        with WorkspaceDatabase.session() as db:
            key = db.get(ApiKey, key_id)
            if key is None:
                return False
            key.revoked = True
            return True


def key_conversation_id(key_id: str, requested: Optional[str], channel: str = "api") -> str:
    """Conversation ids chosen by API callers live in that key's own namespace.

    A key can therefore never read or extend another key's, the owner's or Autopilot's threads.
    """
    prefix = f"key:{key_id}:"
    requested = (requested or "").strip()
    if requested.startswith(prefix):
        return requested
    return f"{prefix}{channel}:{requested or secrets.token_hex(6)}"


# What each scope lets a key's requests do inside the Runtime ("cap" = all actions, "cap:read" = reads).
SCOPE_GRANTS = {
    "records:read": ("contacts:read", "tasks:read"),
    "records:write": ("contacts", "tasks"),
    "events": ("integration_events",),
}
ALWAYS_GRANTED = ("send_message",)  # external, so it still waits for owner approval


def grants_for_scopes(scopes) -> List[str]:
    """Runtime capability grants for an API key; steps outside them wait for the owner (or are denied for reads)."""
    grants = set(ALWAYS_GRANTED)
    for scope in scopes or ():
        grants.update(SCOPE_GRANTS.get(scope, ()))
    return sorted(grants)


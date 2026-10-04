"""B.O.S. API Security v1.0

Owner authentication (password + signed session tokens) and API-key auth for
integrations. Authentication is infrastructure, so exact comparisons are correct here.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from bootstrap.platform import Platform
from integrations.api_keys import KEY_PREFIX, ApiKeyService
from workspace.database import WorkspaceDatabase
from workspace.models import Owner

SESSION_DAYS = 14
PBKDF2_ROUNDS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(rounds))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def _signing_key() -> bytes:
    return hashlib.sha256(f"bos-session::{Platform.settings.secret_key}".encode()).digest()


def issue_session(owner_id: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": owner_id, "exp": int(time.time()) + SESSION_DAYS * 86400}).encode()).decode()
    sig = base64.urlsafe_b64encode(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest()).decode()
    return f"{payload}.{sig}"


def read_session(token: str) -> Optional[str]:
    try:
        payload, sig = token.split(".")
    except ValueError:
        return None
    expected = base64.urlsafe_b64encode(hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return None
    if int(data.get("exp", 0)) < time.time():
        return None
    return str(data.get("sub") or "")


@dataclass
class Principal:
    kind: str  # "owner" | "api_key"
    id: str
    name: str
    scopes: tuple = ()

    def can(self, scope: str) -> bool:
        return self.kind == "owner" or scope in self.scopes


def _bearer(authorization: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def current_principal(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Principal:
    token = x_api_key or _bearer(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required.")
    if token.startswith(KEY_PREFIX):
        key = ApiKeyService.verify(token)  # scopes are enforced per route by require_scope
        if key:
            return Principal(kind="api_key", id=key["id"], name=key["name"], scopes=tuple(key["scopes"]))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key.")
    owner_id = read_session(token)
    if owner_id:
        with WorkspaceDatabase.session() as db:
            owner = db.get(Owner, owner_id)
            if owner:
                return Principal(kind="owner", id=owner.id, name=owner.name)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please sign in again.")


def require_owner(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.kind != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner session required.")
    return principal


def require_scope(scope: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.can(scope):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"API key lacks the '{scope}' scope.")
        return principal

    return dependency

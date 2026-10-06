"""B.O.S. Workspace Vault v1.0

Encrypts integration credentials at rest with a key derived from the platform secret.
"""

import base64
import hashlib
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


class WorkspaceVault:
    """Symmetric encryption for credentials stored in the business database."""

    _fernet: Optional[Fernet] = None

    @classmethod
    def configure(cls, secret_key: str) -> None:
        digest = hashlib.sha256(f"bos-vault::{secret_key}".encode()).digest()
        cls._fernet = Fernet(base64.urlsafe_b64encode(digest))

    @classmethod
    def _require(cls) -> Fernet:
        if cls._fernet is None:
            raise RuntimeError("WorkspaceVault is not configured.")
        return cls._fernet

    @classmethod
    def encrypt(cls, value: str) -> str:
        return cls._require().encrypt(value.encode()).decode()

    @classmethod
    def decrypt(cls, token: str) -> str:
        if not token:
            return ""
        try:
            return cls._require().decrypt(token.encode()).decode()
        except InvalidToken:
            return ""

    @classmethod
    def encrypt_json(cls, data: Dict[str, Any]) -> str:
        return cls.encrypt(json.dumps(data))

    @classmethod
    def decrypt_json(cls, token: str) -> Dict[str, Any]:
        raw = cls.decrypt(token)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}

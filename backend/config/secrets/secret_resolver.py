"""B.O.S. Secret Resolver v0.1

Resolves secrets from local store or external secret managers without logging values.
"""

from typing import Any, Dict, Optional
from .secret_reference import SecretReference


class SecretResolver:
    """Resolver retrieving secrets securely without exposing raw values in logs."""

    _secret_store: Dict[str, str] = {}

    @classmethod
    def register_secret(cls, key: str, value: str) -> None:
        cls._secret_store[key.upper()] = value

    @classmethod
    def resolve(cls, ref: SecretReference | str) -> Optional[str]:
        key = ref.key if isinstance(ref, SecretReference) else ref
        return cls._secret_store.get(key.upper())

    @classmethod
    def clear(cls) -> None:
        cls._secret_store.clear()

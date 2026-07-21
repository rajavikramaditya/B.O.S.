"""B.O.S. Secret Manager v0.1

Centralized manager managing secrets and securely injecting resolved secret values into Providers.
"""

from typing import Any, Dict, Optional
from .secret_reference import SecretReference
from .secret_resolver import SecretResolver


class SecretManager:
    """Manager providing secret access and provider secret injection."""

    @classmethod
    def set_secret(cls, key: str, value: str) -> None:
        SecretResolver.register_secret(key, value)

    @classmethod
    def get_secret(cls, key: str) -> Optional[str]:
        return SecretResolver.resolve(key)

    @classmethod
    def inject_secrets(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Scans config dictionary and resolves any SecretReference instances."""
        resolved = dict(config)
        for k, v in resolved.items():
            if isinstance(v, SecretReference):
                resolved[k] = SecretResolver.resolve(v) or ""
            elif isinstance(v, str) and v.startswith("SECRET::"):
                sec_key = v.replace("SECRET::", "")
                resolved[k] = SecretResolver.resolve(sec_key) or ""
        return resolved

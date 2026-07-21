"""B.O.S. Secret Reference Dataclass v0.1

Encapsulates secret key, vault path, and masking indicator.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SecretReference:
    """Dataclass holding secret reference keys and optional external vault paths."""

    key: str
    vault_path: Optional[str] = None
    is_secret: bool = True

    def __repr__(self) -> str:
        # Mask secret value in repr/logs to protect sensitive data
        return f"SecretReference(key='{self.key}', vault_path='{self.vault_path}', value='***REDACTED***')"

    def __str__(self) -> str:
        return self.__repr__()

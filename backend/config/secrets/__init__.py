"""B.O.S. Secrets Framework Package v0.1

Provides SecretReference, SecretResolver, and SecretManager.
"""

from .secret_reference import SecretReference
from .secret_resolver import SecretResolver
from .secret_manager import SecretManager

__all__ = ["SecretReference", "SecretResolver", "SecretManager"]

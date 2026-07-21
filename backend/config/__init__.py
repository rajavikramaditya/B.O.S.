"""B.O.S. Configuration Framework Package v0.1

Provides BaseConfiguration, ConfigurationMetadata, ConfigurationContext, ConfigurationScope,
ConfigurationSource, RuntimeConfigurationRegistry, ConfigurationLoader, ConfigurationResolver,
SecretReference, SecretResolver, SecretManager, and FeatureFlagManager.
"""

from .base import (
    BaseConfiguration,
    ConfigurationMetadata,
    ConfigurationContext,
    ConfigurationScope,
    ConfigurationSource,
)
from .registry import RuntimeConfigurationRegistry
from .loader import ConfigurationLoader
from .resolver import ConfigurationResolver
from .secrets import SecretReference, SecretResolver, SecretManager
from .flags import FeatureFlagManager

__all__ = [
    "BaseConfiguration",
    "ConfigurationMetadata",
    "ConfigurationContext",
    "ConfigurationScope",
    "ConfigurationSource",
    "RuntimeConfigurationRegistry",
    "ConfigurationLoader",
    "ConfigurationResolver",
    "SecretReference",
    "SecretResolver",
    "SecretManager",
    "FeatureFlagManager",
]

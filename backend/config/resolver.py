"""B.O.S. Configuration Resolver v0.1

Implements 6-tier configuration resolution lookup:
Runtime -> Tenant -> Module -> Provider -> Global -> Default
No hardcoding.
"""

from typing import Any, Dict, Optional
from .base.configuration_context import ConfigurationContext
from .base.configuration_scope import ConfigurationScope
from .registry import RuntimeConfigurationRegistry
from .secrets.secret_manager import SecretManager


class ConfigurationResolver:
    """Hierarchical configuration resolver evaluating 6 lookup scopes."""

    @classmethod
    def resolve_value(
        cls,
        name: str,
        key: str,
        context: Optional[ConfigurationContext] = None,
        default: Any = None,
    ) -> Any:
        ctx = context or ConfigurationContext()

        # Tier 1: Runtime Scope
        cfg = RuntimeConfigurationRegistry.get_config(name, ConfigurationScope.RUNTIME)
        if cfg and cfg.get(key) is not None:
            return cls._clean_val(cfg.get(key))

        # Tier 2: Tenant Scope
        if ctx.tenant_id:
            cfg = RuntimeConfigurationRegistry.get_config(name, ConfigurationScope.TENANT, tenant_id=ctx.tenant_id)
            if cfg and cfg.get(key) is not None:
                return cls._clean_val(cfg.get(key))

        # Tier 3: Module Scope
        if ctx.module_id:
            cfg = RuntimeConfigurationRegistry.get_config(name, ConfigurationScope.MODULE, module_id=ctx.module_id)
            if cfg and cfg.get(key) is not None:
                return cls._clean_val(cfg.get(key))

        # Tier 4: Provider Scope
        if ctx.provider_id:
            cfg = RuntimeConfigurationRegistry.get_config(name, ConfigurationScope.PROVIDER, provider_id=ctx.provider_id)
            if cfg and cfg.get(key) is not None:
                return cls._clean_val(cfg.get(key))

        # Tier 5: Global Scope
        cfg = RuntimeConfigurationRegistry.get_config(name, ConfigurationScope.GLOBAL)
        if cfg and cfg.get(key) is not None:
            return cls._clean_val(cfg.get(key))

        # Tier 6: Default Fallback
        return default

    @classmethod
    def _clean_val(cls, val: Any) -> Any:
        if isinstance(val, dict):
            return SecretManager.inject_secrets(val)
        return val

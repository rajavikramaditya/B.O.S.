"""B.O.S. Runtime Configuration Registry v0.1

Central registry managing normalized BaseConfiguration objects across scopes.
"""

from typing import Any, Dict, List, Optional
from .base.base_configuration import BaseConfiguration
from .base.configuration_scope import ConfigurationScope


class RuntimeConfigurationRegistry:
    """Registry managing platform configuration objects."""

    _configs: Dict[str, BaseConfiguration] = {}

    @classmethod
    def register(cls, config: BaseConfiguration) -> None:
        key = cls._make_key(config.metadata.name, config.metadata.scope, config.metadata.tenant_id, config.metadata.module_id, config.metadata.provider_id)
        cls._configs[key] = config

    @classmethod
    def get_config(
        cls,
        name: str,
        scope: ConfigurationScope = ConfigurationScope.GLOBAL,
        tenant_id: Optional[str] = None,
        module_id: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> Optional[BaseConfiguration]:
        key = cls._make_key(name, scope, tenant_id, module_id, provider_id)
        return cls._configs.get(key)

    @classmethod
    def override_val(
        cls,
        name: str,
        key: str,
        val: Any,
        scope: ConfigurationScope = ConfigurationScope.GLOBAL,
        tenant_id: Optional[str] = None,
    ) -> None:
        cfg = cls.get_config(name, scope, tenant_id)
        if cfg:
            cfg.set(key, val)

    @classmethod
    def _make_key(
        cls,
        name: str,
        scope: ConfigurationScope,
        tenant_id: Optional[str] = None,
        module_id: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> str:
        s_val = scope.value if hasattr(scope, "value") else scope
        t_part = f"_t:{tenant_id.lower()}" if tenant_id else ""
        m_part = f"_m:{module_id.lower()}" if module_id else ""
        p_part = f"_p:{provider_id.lower()}" if provider_id else ""
        return f"{name.lower()}_{s_val}{t_part}{m_part}{p_part}"

    @classmethod
    def clear(cls) -> None:
        cls._configs.clear()

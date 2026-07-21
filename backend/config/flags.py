"""B.O.S. Feature Flag Manager v0.1

Provides platform-native feature flags supporting global, tenant-specific, and module-specific flags.
"""

from typing import Any, Dict, Optional


class FeatureFlagManager:
    """Manages platform feature flags and gradual rollouts."""

    _flags: Dict[str, bool] = {}
    _tenant_flags: Dict[str, Dict[str, bool]] = {}
    _module_flags: Dict[str, Dict[str, bool]] = {}

    @classmethod
    def enable_flag(cls, flag: str) -> None:
        cls._flags[flag.lower()] = True

    @classmethod
    def disable_flag(cls, flag: str) -> None:
        cls._flags[flag.lower()] = False

    @classmethod
    def set_tenant_flag(cls, tenant_id: str, flag: str, enabled: bool) -> None:
        tid = tenant_id.lower()
        if tid not in cls._tenant_flags:
            cls._tenant_flags[tid] = {}
        cls._tenant_flags[tid][flag.lower()] = enabled

    @classmethod
    def set_module_flag(cls, module_id: str, flag: str, enabled: bool) -> None:
        mid = module_id.lower()
        if mid not in cls._module_flags:
            cls._module_flags[mid] = {}
        cls._module_flags[mid][flag.lower()] = enabled

    @classmethod
    def is_enabled(
        cls, flag: str, tenant_id: Optional[str] = None, module_id: Optional[str] = None
    ) -> bool:
        flag_key = flag.lower()
        if tenant_id and tenant_id.lower() in cls._tenant_flags:
            if flag_key in cls._tenant_flags[tenant_id.lower()]:
                return cls._tenant_flags[tenant_id.lower()][flag_key]

        if module_id and module_id.lower() in cls._module_flags:
            if flag_key in cls._module_flags[module_id.lower()]:
                return cls._module_flags[module_id.lower()][flag_key]

        return cls._flags.get(flag_key, False)

    @classmethod
    def clear(cls) -> None:
        cls._flags.clear()
        cls._tenant_flags.clear()
        cls._module_flags.clear()

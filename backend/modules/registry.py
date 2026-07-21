"""B.O.S. Runtime Module Registry v0.1

Central registry managing installed business modules.
Runtime NEVER hardcodes modules.
"""

from typing import Any, Dict, List, Optional
from .base import BaseModule, ModuleLifecycle
from .events import ModuleEventPublisher, ModuleEventType


class RuntimeModuleRegistry:
    """Stores and resolves runtime business modules."""

    _modules: Dict[str, BaseModule] = {}

    @classmethod
    def register(cls, module: BaseModule) -> None:
        name = module.manifest.name.lower()
        cls._modules[name] = module
        if module.state.status == ModuleLifecycle.UNLOADED:
            module.state.status = ModuleLifecycle.REGISTERED
        ModuleEventPublisher.publish(ModuleEventType.MODULE_INSTALLED, name)

    @classmethod
    def get(cls, name: str) -> Optional[BaseModule]:
        return cls._modules.get(name.lower())

    @classmethod
    def enable_module(cls, name: str) -> bool:
        mod = cls.get(name)
        if mod:
            success = mod.enable()
            if success:
                ModuleEventPublisher.publish(ModuleEventType.MODULE_ENABLED, name)
            return success
        return False

    @classmethod
    def disable_module(cls, name: str) -> bool:
        mod = cls.get(name)
        if mod:
            success = mod.disable()
            if success:
                ModuleEventPublisher.publish(ModuleEventType.MODULE_DISABLED, name)
            return success
        return False

    @classmethod
    def unload_module(cls, name: str) -> bool:
        name_lower = name.lower()
        mod = cls.get(name_lower)
        if mod:
            mod.unload()
            del cls._modules[name_lower]
            ModuleEventPublisher.publish(ModuleEventType.MODULE_REMOVED, name_lower)
            return True
        return False

    @classmethod
    def resolve_dependencies(cls, name: str) -> List[str]:
        mod = cls.get(name)
        if not mod:
            return []
        deps = mod.manifest.dependencies
        missing = [d for d in deps if not cls.get(d)]
        return missing

    @classmethod
    def list_modules(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": mod.manifest.name,
                "version": mod.manifest.version,
                "status": mod.state.status.value,
                "active": mod.state.active,
            }
            for mod in cls._modules.values()
        ]

    @classmethod
    def clear(cls) -> None:
        cls._modules.clear()

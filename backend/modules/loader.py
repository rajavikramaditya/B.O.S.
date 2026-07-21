"""B.O.S. Module Loader v0.1

Validates manifest, verifies dependencies, instantiates module, injects context,
registers capabilities in sandbox, and registers module in RuntimeModuleRegistry.
"""

from typing import Any, Dict, Type
from .base import BaseModule, ModuleContext, ModuleManifest, ModuleLifecycle
from .registry import RuntimeModuleRegistry
from .sandbox import ModuleSandbox
from .events import ModuleEventPublisher, ModuleEventType
from runtime.events import RuntimeEventBus
from runtime.registry import UniversalCapabilityRegistry
from runtime.policy import PolicyEngineV2


class ModuleLoader:
    """Instantiates and initializes business modules."""

    @classmethod
    def load_module(cls, module_class: Type[BaseModule], manifest_dict: Dict[str, Any]) -> BaseModule:
        manifest = ModuleManifest.from_dict(manifest_dict)
        if not manifest.validate():
            raise ValueError(f"Invalid module manifest for '{manifest.name}'")

        module = module_class(manifest)

        # Sandbox compliance check
        if not ModuleSandbox.validate_sandbox_compliance(module):
            raise PermissionError(f"Module '{manifest.name}' failed sandbox validation.")

        # Register capabilities declared in manifest
        for cap in manifest.capabilities:
            ModuleSandbox.register_module_capability(cap, f"Capability for module {manifest.name}")

        # Construct and inject context
        context = ModuleContext(
            module_id=manifest.name,
            event_bus=RuntimeEventBus,
            capability_registry=UniversalCapabilityRegistry,
            policy_engine=PolicyEngineV2,
            settings=manifest.settings,
        )

        module.initialize(context)
        RuntimeModuleRegistry.register(module)
        ModuleEventPublisher.publish(ModuleEventType.MODULE_LOADED, manifest.name)
        return module

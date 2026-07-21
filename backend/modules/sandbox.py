"""B.O.S. Module Sandbox v0.1

Provides isolation and capability registration boundaries for installable modules.
Modules MAY register capabilities, workflows, entities, policies, commands.
Modules MUST NOT modify Runtime, Graphs, Kernel, or Core services.
"""

from typing import Any, Dict, List
from runtime.registry import UniversalCapabilityRegistry, CapabilityMetadata, UniversalCapability
from runtime.policy import PolicyEngineV2
from .base import BaseModule, ModuleContext


class ModuleSandbox:
    """Enforces sandbox boundaries and delegates extension registration."""

    @classmethod
    def register_module_capability(cls, capability_name: str, description: str = "") -> None:
        """Register a module-provided capability in UniversalCapabilityRegistry."""
        if not UniversalCapabilityRegistry.get(capability_name):
            meta = CapabilityMetadata(name=capability_name, description=description)

            class GenericModuleCapability(UniversalCapability):
                def supported_actions(self) -> List[str]:
                    return ["create", "read", "update", "delete", "execute"]

                def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
                    return {"status": "SUCCESS", "capability": capability_name, "action": action, "params": params}

            cap = GenericModuleCapability(meta)
            UniversalCapabilityRegistry.register(cap)

    @classmethod
    def register_module_policy(cls, policy_name: str, rule: Any) -> None:
        """Register a module-provided policy rule."""
        PolicyEngineV2.register_custom_policy(policy_name, rule)

    @classmethod
    def validate_sandbox_compliance(cls, module: BaseModule) -> bool:
        """Validate that module does not violate sandbox isolation rules."""
        forbidden_terms = ["_BOSRuntimeEngine", "_Kernel", "_GraphStore"]
        module_str = str(dir(module))
        for term in forbidden_terms:
            if term in module_str:
                return False
        return True

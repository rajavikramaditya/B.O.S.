"""B.O.S. Provider-Backed Capability v1.0

Shared implementation for capabilities whose actions are fulfilled by whichever
provider is registered for a provider capability. Declares per-action risk and
parameters so the Runtime planner and policy can reason about it generically.
"""

from typing import Any, Dict, List

from capabilities.base.base_capability import BaseCapability
from capabilities.base.capability_context import CapabilityContext
from capabilities.base.capability_metadata import CapabilityMetadata
from capabilities.base.capability_result import CapabilityResult
from capabilities.base.capability_scope import CapabilityScope


class ProviderBackedCapability(BaseCapability):
    """Capability that maps its actions 1:1 onto a provider capability."""

    def __init__(
        self,
        *,
        name: str,
        category: str,
        description: str,
        provider_capability: str,
        actions: Dict[str, Dict[str, Any]],
        planner_visible: bool = True,
    ):
        """actions: {action: {"risk": read|safe|external|sensitive, "params": {...}, "self_service": param}}"""
        self._provider_capability = provider_capability
        self._actions = actions
        super().__init__(
            metadata=CapabilityMetadata(
                name=name,
                version="1.0.0",
                category=category,
                description=description,
                required_providers=[provider_capability],
                scope=CapabilityScope.GLOBAL,
                configuration=_declarations(actions, planner_visible),
            )
        )

    def supported_actions(self) -> List[str]:
        return list(self._actions)

    def execute(self, action: str, params: Dict[str, Any], context: CapabilityContext) -> CapabilityResult:
        from providers.resolver import ProviderResolver

        result = ProviderResolver.execute_capability(self._provider_capability, action, params)
        return CapabilityResult(
            success=bool(result.get("success", False)),
            capability_name=self.name,
            action=action,
            data=result,
            message=str(result.get("message", "")),
            error=result.get("error"),
            provider_used=result.get("resolved_provider"),
            correlation_id=context.correlation_id,
        )


def declare_actions(capability: BaseCapability, actions: Dict[str, Dict[str, Any]], planner_visible: bool = True) -> None:
    """Attach planner/policy declarations to an existing capability (e.g. reference capabilities)."""
    capability.metadata.configuration.update(_declarations(actions, planner_visible))


def _declarations(actions: Dict[str, Dict[str, Any]], planner_visible: bool) -> Dict[str, Any]:
    """Planner/policy metadata.

    spec keys: risk, params, and optional self_service — the parameter the Runtime pins to
    the requesting customer's own contact id, so customers can only act on their own record.
    """
    return {
        "planner_visible": planner_visible,
        "action_risk": {a: spec.get("risk", "external") for a, spec in actions.items()},
        "action_params": {a: spec.get("params", {}) for a, spec in actions.items()},
        "self_service": {a: spec["self_service"] for a, spec in actions.items() if spec.get("self_service")},
    }

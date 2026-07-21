"""B.O.S. Capability Resolver v0.1

Resolves capabilities and delegates execution to ProviderResolver.

Execution Flow:
    Business Module
        ↓
    CapabilityResolver.execute()
        ↓
    RuntimeCapabilityRegistry  (find capability)
        ↓
    CapabilityPolicyManager    (validate policies)
        ↓
    BaseCapability.execute_safe()
        ↓
    ProviderResolver           (inside capability implementation)
        ↓
    BaseProvider.execute()

The Resolver never references specific vendor names.
"""

from typing import Any, Dict, Optional

from .base.capability_context import CapabilityContext
from .base.capability_result import CapabilityResult
from .events import CapabilityEventPublisher, CapabilityEventType
from .policies import CapabilityPolicyManager
from .registry import RuntimeCapabilityRegistry


class CapabilityResolver:
    """Resolves capability requests and delegates execution."""

    @classmethod
    def resolve(cls, name: str) -> Optional[Any]:
        """Resolve a capability by name.

        Returns the BaseCapability instance if enabled, None otherwise.
        """
        return RuntimeCapabilityRegistry.get(name)

    @classmethod
    def execute(
        cls,
        capability_name: str,
        action: str,
        params: Dict[str, Any],
        context: Optional[CapabilityContext] = None,
    ) -> CapabilityResult:
        """Execute a capability action via the full resolution pipeline.

        Steps:
        1. Resolve capability from registry
        2. Validate policies
        3. Execute safely via BaseCapability.execute_safe()
        4. Publish execution events
        """
        ctx = context or CapabilityContext()

        # Step 1: Resolve capability
        capability = RuntimeCapabilityRegistry.get(capability_name)
        if not capability:
            result = CapabilityResult.failure(
                capability_name=capability_name,
                action=action,
                error=f"Capability '{capability_name}' not found or not enabled.",
                correlation_id=ctx.correlation_id,
            )
            CapabilityEventPublisher.publish(
                CapabilityEventType.CAPABILITY_FAILED,
                capability_name,
                {"action": action, "error": result.error},
            )
            return result

        # Step 2: Validate action is supported
        if not capability.supports_action(action):
            result = CapabilityResult.failure(
                capability_name=capability_name,
                action=action,
                error=(
                    f"Action '{action}' is not supported by capability '{capability_name}'. "
                    f"Supported: {capability.supported_actions()}"
                ),
                correlation_id=ctx.correlation_id,
            )
            CapabilityEventPublisher.publish(
                CapabilityEventType.CAPABILITY_FAILED,
                capability_name,
                {"action": action, "error": result.error},
            )
            return result

        # Step 3: Validate policies
        allowed, reason = CapabilityPolicyManager.validate(
            capability_name=capability_name,
            context=ctx,
            metadata=capability.metadata,
        )
        if not allowed:
            result = CapabilityResult.failure(
                capability_name=capability_name,
                action=action,
                error=f"Policy blocked capability '{capability_name}': {reason}",
                correlation_id=ctx.correlation_id,
            )
            CapabilityEventPublisher.publish(
                CapabilityEventType.CAPABILITY_FAILED,
                capability_name,
                {"action": action, "error": result.error, "policy_reason": reason},
            )
            return result

        # Step 4: Execute
        CapabilityEventPublisher.publish(
            CapabilityEventType.CAPABILITY_RESOLVED,
            capability_name,
            {"action": action, "correlation_id": ctx.correlation_id},
        )
        result = capability.execute_safe(action, params, ctx)

        # Step 5: Publish result event
        if not result.success:
            CapabilityEventPublisher.publish(
                CapabilityEventType.CAPABILITY_FAILED,
                capability_name,
                {"action": action, "error": result.error},
            )

        return result

    @classmethod
    def execute_for_action(
        cls,
        action: str,
        params: Dict[str, Any],
        context: Optional[CapabilityContext] = None,
    ) -> CapabilityResult:
        """Find the first capability supporting the action and execute it."""
        ctx = context or CapabilityContext()
        capability = RuntimeCapabilityRegistry.resolve_for_action(action)

        if not capability:
            return CapabilityResult.failure(
                capability_name="unknown",
                action=action,
                error=f"No enabled capability found supporting action '{action}'.",
                correlation_id=ctx.correlation_id,
            )

        return cls.execute(capability.name, action, params, ctx)

"""B.O.S. SendMessageCapability v0.1

Reference capability for cross-channel messaging.
Delegates all execution to ProviderResolver — never calls WhatsApp/Telegram/Email APIs directly.
"""

from typing import Any, Dict, List

from capabilities.base.base_capability import BaseCapability
from capabilities.base.capability_context import CapabilityContext
from capabilities.base.capability_metadata import CapabilityMetadata
from capabilities.base.capability_result import CapabilityResult
from capabilities.base.capability_scope import CapabilityScope


class SendMessageCapability(BaseCapability):
    """Platform capability for cross-channel message delivery.

    Business Modules may send messages without knowing which
    messaging provider (WhatsApp, Telegram, Email, SMS) will deliver it.
    """

    def __init__(self):
        super().__init__(
            metadata=CapabilityMetadata(
                name="send_message",
                version="1.0.0",
                category="messaging",
                description="Cross-channel message delivery: WhatsApp, Telegram, Email, SMS.",
                required_providers=["messaging"],
                permissions=[],
                scope=CapabilityScope.GLOBAL,
            )
        )

    def supported_actions(self) -> List[str]:
        return ["send", "broadcast", "notify"]

    def execute(
        self, action: str, params: Dict[str, Any], context: CapabilityContext
    ) -> CapabilityResult:
        """Delegate execution to ProviderResolver — never calls messaging APIs directly."""
        try:
            from providers.resolver import ProviderResolver

            result = ProviderResolver.execute_capability(
                capability="messaging",
                action=action,
                params=params,
            )
            return CapabilityResult(
                success=result.get("success", False),
                capability_name=self.name,
                action=action,
                data=result,
                message=result.get("message", ""),
                error=result.get("error"),
                provider_used=result.get("resolved_provider"),
                correlation_id=context.correlation_id,
            )
        except Exception as ex:
            return CapabilityResult.failure(
                capability_name=self.name,
                action=action,
                error=f"SendMessageCapability execution failed: {str(ex)}",
                correlation_id=context.correlation_id,
            )

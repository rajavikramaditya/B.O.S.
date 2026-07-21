"""B.O.S. Messaging Capability v0.1

Provides generic messaging actions across communication channels.
"""

from typing import Any, Dict, List
from .base import BaseCapability, CapabilityResult, CapabilityRegistry


class MessagingCapability(BaseCapability):
    """Platform Messaging Capability."""

    def __init__(self):
        super().__init__(
            name="messaging",
            description="Generic communication and messaging capability across channels.",
        )

    def supported_actions(self) -> List[str]:
        return [
            "send_message",
            "notify_owner",
            "customer_whatsapp_recall",
            "arm_deferred_status",
        ]

    def execute(self, action: str, params: Dict[str, Any]) -> CapabilityResult:
        if action == "customer_whatsapp_recall":
            from services.brain.owner_customer_context import build_customer_recall_packet

            owner_msg = params.get("message", "")
            out = build_customer_recall_packet(owner_message=owner_msg)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=out,
                message=out.get("fallback_line", "Messaging completed."),
            )

        if action == "notify_owner":
            from services.brain.owner_notifier import notify_owner

            text = params.get("text", "") or params.get("message", "")
            ok = notify_owner(text)
            return CapabilityResult(
                success=ok,
                capability_name=self.name,
                action=action,
                data={"delivered": ok},
                message="Owner notified." if ok else "Notification failed.",
            )

        if action == "arm_deferred_status":
            from services.tools.deferred_whatsapp_status import handle_arm_deferred_status

            res = handle_arm_deferred_status(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Deferred status armed."),
            )

        return CapabilityResult(
            success=False,
            capability_name=self.name,
            action=action,
            error=f"Action '{action}' not implemented in MessagingCapability.",
        )


CapabilityRegistry.register(MessagingCapability())

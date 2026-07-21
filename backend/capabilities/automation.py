"""B.O.S. Automation Capability v0.1

Provides station operations, system automation, and workflow execution actions.
"""

from typing import Any, Dict, List
from .base import BaseCapability, CapabilityResult, CapabilityRegistry


class AutomationCapability(BaseCapability):
    """Platform Automation Capability."""

    def __init__(self):
        super().__init__(
            name="automation",
            description="Generic operational automation and live execution capability.",
        )

    def supported_actions(self) -> List[str]:
        return [
            "now_playing",
            "azuracast_pulse",
            "stream_listener_status",
            "send_azuracast",
            "approve_latest_script",
            "approve_capsule",
            "generate_audio",
            "prepare_capsule_audio",
        ]

    def execute(self, action: str, params: Dict[str, Any]) -> CapabilityResult:
        if action == "now_playing":
            from services.tools.live_ops import handle_now_playing

            res = handle_now_playing(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Now playing status retrieved."),
            )

        if action in ("send_azuracast", "approve_latest_script", "approve_capsule", "generate_audio", "prepare_capsule_audio"):
            from services.brain.operations_workflows import handle_operations_workflow

            res = handle_operations_workflow(action, params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res if isinstance(res, dict) else {"result": res},
                message=res.get("reply", "") if isinstance(res, dict) else str(res),
            )

        return CapabilityResult(
            success=False,
            capability_name=self.name,
            action=action,
            error=f"Action '{action}' not implemented in AutomationCapability.",
        )


CapabilityRegistry.register(AutomationCapability())

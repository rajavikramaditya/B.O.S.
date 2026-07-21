"""B.O.S. Scheduling Capability v0.1

Provides scheduling, event, and calendar management actions.
"""

from typing import Any, Dict, List
from .base import BaseCapability, CapabilityResult, CapabilityRegistry


class SchedulingCapability(BaseCapability):
    """Platform Scheduling Capability."""

    def __init__(self):
        super().__init__(
            name="scheduling",
            description="Generic scheduling and calendar event management capability.",
        )

    def supported_actions(self) -> List[str]:
        return [
            "get_station_schedule",
            "whats_next",
            "assign_capsule_to_playlist",
        ]

    def execute(self, action: str, params: Dict[str, Any]) -> CapabilityResult:
        if action == "get_station_schedule":
            from services.tools.live_ops import handle_get_station_schedule

            res = handle_get_station_schedule(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Schedule retrieved."),
            )

        if action == "whats_next":
            from services.tools.live_ops import handle_whats_next

            res = handle_whats_next(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Next playing retrieved."),
            )

        if action == "assign_capsule_to_playlist":
            from services.tools.live_ops import handle_assign_capsule_to_playlist

            res = handle_assign_capsule_to_playlist(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Playlist assignment processed."),
            )

        return CapabilityResult(
            success=False,
            capability_name=self.name,
            action=action,
            error=f"Action '{action}' not implemented in SchedulingCapability.",
        )


CapabilityRegistry.register(SchedulingCapability())

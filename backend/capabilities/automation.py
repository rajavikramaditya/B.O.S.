"""B.O.S. Automation Capability v0.1

Provides station operations, system automation, and workflow execution actions.

NOTE: Uses legacy base.py loaded directly to avoid conflict with base/ sub-package.
Pending migration to Radio Business Module (Sprint-13).
"""

import importlib.util as _ilu
import pathlib as _pl
from typing import Any, Dict, List

def _load_legacy():
    _p = _pl.Path(__file__).parent / "base.py"
    spec = _ilu.spec_from_file_location("capabilities._legacy_base", _p)
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_lb = _load_legacy()
BaseCapability = _lb.BaseCapability
CapabilityResult = _lb.CapabilityResult
CapabilityRegistry = _lb.CapabilityRegistry


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

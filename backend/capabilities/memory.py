"""B.O.S. Memory Capability v0.1

Provides memory management, recall, and state awareness actions.

NOTE: Uses legacy base.py loaded directly to avoid conflict with base/ sub-package.
Pending migration to AI Manager Module (Sprint-15+).
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


class MemoryCapability(BaseCapability):
    """Platform Memory Capability."""

    def __init__(self):
        super().__init__(
            name="memory",
            description="Generic memory storage, recall, and self-state capability.",
        )

    def supported_actions(self) -> List[str]:
        return [
            "self_change_status",
            "notebook_self_summary",
            "notebook_day_recap",
            "notebook_future_intentions",
        ]

    def execute(self, action: str, params: Dict[str, Any]) -> CapabilityResult:
        if action == "self_change_status":
            from services.tools.self_change_status import handle_self_change_status

            res = handle_self_change_status(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Self change status retrieved."),
            )

        if action in ("notebook_self_summary", "notebook_day_recap", "notebook_future_intentions"):
            from services.tools.memory_notebook import (
                handle_notebook_self_summary,
                handle_notebook_day_recap,
                handle_notebook_future_intentions,
            )

            handlers = {
                "notebook_self_summary": handle_notebook_self_summary,
                "notebook_day_recap": handle_notebook_day_recap,
                "notebook_future_intentions": handle_notebook_future_intentions,
            }
            handler = handlers[action]
            res = handler(params)
            return CapabilityResult(
                success=True,
                capability_name=self.name,
                action=action,
                data=res,
                message=res.get("reply", "Notebook retrieved."),
            )

        return CapabilityResult(
            success=False,
            capability_name=self.name,
            action=action,
            error=f"Action '{action}' not implemented in MemoryCapability.",
        )


CapabilityRegistry.register(MemoryCapability())

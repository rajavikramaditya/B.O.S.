"""B.O.S. Step Runner v0.1

Executes individual plan steps, handles pause for approval, retries, and skips.
"""

from typing import Any, Dict
from ..contracts import PlanStep
from adapters import AdapterRouter
from .executor_state import ExecutorState, ExecutorStatus


class StepRunner:
    """Executes single plan step via Capability / Adapter layer."""

    @classmethod
    def run_step(cls, step: PlanStep, state: ExecutorState, role: str = "customer") -> Dict[str, Any]:
        # Check approval requirement
        if step.params and step.params.get("requires_approval") and role == "owner":
            state.status = ExecutorStatus.WAITING_APPROVAL
            return {"status": "WAITING_APPROVAL", "step": step.action}

        # Route step action to adapters
        res = AdapterRouter.route_action(
            action=step.action,
            channel=step.params.get("channel", "default") if step.params else "default",
            recipient=step.params.get("recipient", "") if step.params else "",
            payload=step.params or {},
        )

        if res.success:
            return {"status": "SUCCESS", "action": step.action, "data": res.data}
        else:
            return {"status": "FAILED", "action": step.action, "error": res.error_message}

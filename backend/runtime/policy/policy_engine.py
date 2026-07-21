"""B.O.S. Policy Engine v2

Modular policy evaluation engine combining Security, Approval, Permissions, Business, and Execution policies.
"""

from typing import Any, Dict, List
from .security import SecurityPolicy
from .approval import ApprovalPolicy
from .permissions import PermissionsPolicy
from .business import BusinessPolicy
from .execution import ExecutionPolicy


class PolicyEngineV2:
    """Evaluates modular policies returning ALLOW, DENY, CONFIRM, or ESCALATE."""

    @classmethod
    def evaluate(
        cls,
        action: str,
        params: Dict[str, Any],
        role: str = "customer",
        raw_text: str = "",
        permissions: List[str] | None = None,
    ) -> Dict[str, Any]:
        # Priority order: Security -> Permissions -> Business -> Execution -> Approval
        sec_res = SecurityPolicy.evaluate(action, params, raw_text)
        if sec_res == "DENY":
            return {"status": "DENY", "reason": "Security policy violation", "protected": True}

        perm_res = PermissionsPolicy.evaluate(action, role, permissions)
        if perm_res == "DENY":
            return {"status": "DENY", "reason": "Insufficient permissions for role", "protected": False}

        biz_res = BusinessPolicy.evaluate(action, params)
        if biz_res == "DENY":
            return {"status": "DENY", "reason": "Business policy violation", "protected": False}

        exec_res = ExecutionPolicy.evaluate(action, params)
        if exec_res == "ESCALATE":
            return {"status": "ESCALATE", "reason": "Execution policy escalation required", "protected": False}

        app_res = ApprovalPolicy.evaluate(action, params, role)
        if app_res == "CONFIRM":
            return {
                "status": "CONFIRM",
                "reason": f"Action '{action}' requires owner confirmation",
                "protected": True,
                "require_confirmation": True,
            }

        return {"status": "ALLOW", "reason": "All policies passed", "protected": False}

    @classmethod
    def evaluate_request(
        cls,
        action: str,
        params: Dict[str, Any],
        role: str = "customer",
        raw_text: str = "",
        permissions: List[str] | None = None,
    ) -> Any:
        from ..contracts import PolicyDecision
        res = cls.evaluate(action, params, role, raw_text, permissions)
        return PolicyDecision(
            status=res.get("status", "ALLOW"),
            action=action,
            reason=res.get("reason", ""),
            protected=bool(res.get("protected")),
            requires_confirmation=bool(res.get("require_confirmation")),
        )


class PolicyEngine:
    """Stage 6 Lifecycle wrapper delegating to PolicyEngineV2."""

    @staticmethod
    def validate_policy(plan, context) -> Any:
        from ..contracts import PolicyDecision

        if not plan or not plan.steps:
            return PolicyDecision(status="ALLOW", action="none", protected=False)

        first_step = plan.steps[0]
        action = first_step.action

        role = "customer"
        if context and hasattr(context, "owner_preferences") and context.owner_preferences:
            role = "owner"

        return PolicyEngineV2.evaluate_request(
            action=action,
            params=first_step.params or {},
            role=role,
        )

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
    """Stage 6 Lifecycle wrapper: evaluates every plan step independently.

    Steps are split into allowed (run now), pending (wait for a human) and denied.
    """

    @staticmethod
    def validate_policy(
        plan, context, role: str | None = None, raw_text: str = "", actor_ref: str = "", grants: list | None = None
    ) -> Any:
        from ..cognition import RuntimeCognition
        from ..contracts import PolicyDecision

        if not plan or not plan.steps:
            return PolicyDecision(status="ALLOW", action="none", reason="No steps planned.", protected=False)

        if role is None:
            role = "owner" if context and getattr(context, "owner_preferences", None) else "customer"
        mode = getattr(context, "autopilot_mode", "autopilot") if context else "autopilot"

        allowed, pending, denied = [], [], []
        for step in plan.steps:
            if step.risk == "unknown":
                denied.append({"step_id": step.step_id, "reason": f"'{step.capability}.{step.action}' is not an available capability."})
                continue
            if step.risk == "read" and not PolicyEngine._role_may_read(role):
                denied.append({"step_id": step.step_id, "reason": "Business records are not readable from this conversation."})
                continue
            if not plan.preapproved and not PolicyEngine._granted(grants, step):
                if step.risk == "read":
                    denied.append({"step_id": step.step_id, "reason": f"This caller may not read '{step.capability}'."})
                else:
                    pending.append(step)  # outside the caller's grant: the owner decides
                continue
            if role == "customer" and step.risk == "safe" and not plan.preapproved:
                # Untrusted actors may only change their own record; anything else waits for the owner.
                pin = RuntimeCognition.self_service_param(step.capability, step.action)
                if not pin or not actor_ref:
                    pending.append(step)
                    continue
                fields = RuntimeCognition.self_service_fields(step.capability, step.action)
                kept = {k: v for k, v in (step.params or {}).items() if k in fields}
                step.params = {**kept, pin: actor_ref}
            verdict = PolicyEngineV2.evaluate(
                action=step.action,
                params=step.params or {},
                role=role,
                raw_text=raw_text,
                permissions=[step.action],
            )
            if verdict["status"] in ("DENY", "ESCALATE") and not (
                verdict["status"] == "ESCALATE" and step.risk in ("external", "sensitive")
            ):
                denied.append({"step_id": step.step_id, "reason": verdict.get("reason", "Policy denied.")})
            elif verdict["status"] in ("CONFIRM", "ESCALATE"):
                pending.append(step)
            elif not plan.preapproved and (
                ApprovalPolicy.requires_human(step.risk, mode) or not PolicyEngine._role_may_act(role, step.risk)
            ):
                pending.append(step)
            else:
                allowed.append(step)

        status = "ALLOW" if not pending and not denied else ("CONFIRM" if pending else "PARTIAL")
        if not allowed and not pending and denied:
            status = "DENY"
        return PolicyDecision(
            status=status,
            action=plan.steps[0].action,
            reason=f"{len(allowed)} allowed, {len(pending)} awaiting approval, {len(denied)} denied.",
            protected=bool(pending),
            requires_confirmation=bool(pending),
            allowed_steps=allowed,
            pending_steps=pending,
            denied_steps=denied,
        )

    @staticmethod
    def _granted(grants: list | None, step: Any) -> bool:
        if grants is None:
            return True
        return (
            step.capability in grants
            or f"{step.capability}.{step.action}" in grants
            or (step.risk == "read" and f"{step.capability}:read" in grants)
        )

    @staticmethod
    def _role_may_read(role: str) -> bool:
        """Customers only ever see their own context, which the Runtime already provides."""
        return role in ("owner", "employee", "system")

    @staticmethod
    def _role_may_act(role: str, risk: str) -> bool:
        """Owners and the platform may act directly; others run read/safe steps and request the rest."""
        if role in ("owner", "system"):
            return True
        return risk in ("read", "safe")

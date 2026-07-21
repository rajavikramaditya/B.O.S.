"""B.O.S. Execution Engine v0.1

Stage 8 of Runtime Lifecycle: Executes approved capability steps through adapters/tools.
"""

from .contracts import (
    NormalizedRequest,
    ExecutionPlan,
    PolicyDecision,
    CapabilitySelection,
    RuntimeContext,
    ExecutionResult,
)


class ExecutionEngine:
    """Executes approved platform capabilities and records results."""

    @staticmethod
    def execute_plan(
        request: NormalizedRequest,
        plan: ExecutionPlan,
        policy: PolicyDecision,
        capabilities: CapabilitySelection,
        context: RuntimeContext,
    ) -> ExecutionResult:
        if request.role == "customer":
            from services.brain.customer_chat import generate_customer_reply

            res = generate_customer_reply(
                request.message,
                sender_name=request.sender_name or "ji",
                phone=request.phone or "",
            )
            return ExecutionResult(
                success=True,
                action_type=res.get("action_type", "CUSTOMER_CHAT"),
                reply=res.get("reply", ""),
                factual_packet=res.get("factual_packet", {}),
                raw_result=res,
            )

        if request.role == "employee":
            return ExecutionResult(
                success=True,
                action_type="EMPLOYEE_STUB",
                reply="Employee channel abhi active nahi hai. Station ops ke liye owner se baat karein.",
            )

        # Owner execution path using brain's existing owner pipeline
        from services.brain.brain import process_owner_message

        res = process_owner_message(
            request.message,
            selected_model=request.selected_model,
            channel=request.channel,
        )
        return ExecutionResult(
            success=True,
            action_type=res.get("action_type", "UNKNOWN"),
            reply=res.get("reply", ""),
            factual_packet=res.get("factual_packet", {}) or {},
            job_id=res.get("job_id"),
            command_triggered=res.get("command_triggered"),
            approval_id=res.get("approval_id"),
            capsule_id=res.get("capsule_id"),
            approval_status=res.get("approval_status"),
            azuracast_status=res.get("azuracast_status"),
            raw_result=res,
        )

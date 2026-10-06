"""B.O.S. Verification Engine v1.0

Stage 9 of Runtime Lifecycle: Verifies every executed step from its real result.
Only verified outcomes may be reported as done.
"""

from .contracts import ExecutionResult, NormalizedRequest, VerificationReport

RETRYABLE_RISKS = ("read", "safe")


class VerificationEngine:
    """Checks step outcomes and marks which failures are safe to retry."""

    @staticmethod
    def verify(request: NormalizedRequest, execution_result: ExecutionResult) -> VerificationReport:
        failed = [r for r in execution_result.step_results if not r.get("success")]
        retryable = [r["step_id"] for r in failed if r.get("risk") in RETRYABLE_RISKS]
        if not execution_result.step_results:
            truth = "NO_ACTIONS"
        elif failed:
            truth = "PARTIAL" if len(failed) < len(execution_result.step_results) else "FAILED"
        else:
            truth = "VERIFIED"
        return VerificationReport(
            verified=not failed,
            truth_level=truth,
            notes="; ".join(f"step {r['step_id']}: {r.get('error') or 'failed'}" for r in failed),
            factual_packet=execution_result.factual_packet,
            action_type=execution_result.action_type,
            failed_steps=failed,
            retryable_steps=retryable,
        )

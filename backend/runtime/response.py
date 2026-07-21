"""B.O.S. Response Engine v0.1

Stage 11 of Runtime Lifecycle: Composes the final verified RuntimeResponse.
"""

from .contracts import (
    NormalizedRequest,
    VerificationReport,
    ExecutionResult,
    RuntimeResponse,
)


class ResponseEngine:
    """Formats the final response payload for callers."""

    @staticmethod
    def generate_response(
        request: NormalizedRequest,
        verification: VerificationReport,
        execution_result: ExecutionResult,
    ) -> RuntimeResponse:
        raw = execution_result.raw_result if isinstance(execution_result.raw_result, dict) else {}
        resp = RuntimeResponse(
            reply=verification.scrubbed_reply or execution_result.reply,
            action_type=verification.action_type or execution_result.action_type or "UNKNOWN",
            factual_packet=verification.factual_packet or execution_result.factual_packet or {},
            route=raw.get("route", "runtime"),
            source=raw.get("source", "bos_runtime"),
            role=request.role,
            trace={
                "request_id": request.request_id,
                "truth_level": verification.truth_level,
            },
        )
        return resp

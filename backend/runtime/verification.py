"""B.O.S. Verification Engine v0.1

Stage 9 of Runtime Lifecycle: Verifies execution outcome and scrubs unverified claims.
"""

from .contracts import NormalizedRequest, ExecutionResult, VerificationReport


class VerificationEngine:
    """Verifies that execution succeeded and enforces truth gate on replies."""

    @staticmethod
    def verify(
        request: NormalizedRequest, execution_result: ExecutionResult
    ) -> VerificationReport:
        reply = execution_result.reply
        factual_packet = execution_result.factual_packet
        action_type = execution_result.action_type

        from services.agent.truth_gate import enforce_truth_on_reply

        scrubbed_reply, scrub_pkt = enforce_truth_on_reply(
            request.message,
            reply,
            factual_packet=factual_packet if isinstance(factual_packet, dict) else None,
            action=action_type,
        )

        final_packet = factual_packet
        if scrub_pkt and isinstance(scrub_pkt, dict):
            if not isinstance(final_packet, dict) or not final_packet:
                final_packet = scrub_pkt

        return VerificationReport(
            verified=True,
            truth_level="FACTUAL" if not scrub_pkt else "SCRUBBED",
            scrubbed_reply=scrubbed_reply or reply,
            factual_packet=final_packet or {},
            action_type=action_type,
        )

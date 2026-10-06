"""B.O.S. Memory Engine v1.0

Stage 10 of Runtime Lifecycle: Persists the conversation turn and verified outcomes
through the `conversation_memory` capability. Memory never writes business records.
"""

from typing import Any, Dict, List

from .contracts import MemoryUpdate, NormalizedRequest, RuntimeContext, VerificationReport


class MemoryEngine:
    """Persists execution outcomes and context into long-term memory."""

    @staticmethod
    def update_memory(
        request: NormalizedRequest,
        verification: VerificationReport,
        context: RuntimeContext,
        step_results: List[Dict[str, Any]] | None = None,
    ) -> MemoryUpdate:
        if not request.message:
            return MemoryUpdate(saved=False, persisted=False)
        outcomes = [
            {"title": r.get("title"), "success": r.get("success"), "error": r.get("error")}
            for r in (step_results or [])
        ]
        ok = MemoryEngine._append(
            request,
            role="user",
            content=request.message,
            meta={"sender": request.sender_name, "role": request.role, "outcomes": outcomes, "truth": verification.truth_level},
        )
        return MemoryUpdate(saved=ok, persisted=ok, memory_key=request.conversation_id, autosaved_facts=outcomes)

    @staticmethod
    def remember_reply(request: NormalizedRequest, reply: str, meta: Dict[str, Any] | None = None) -> bool:
        if not reply:
            return False
        return MemoryEngine._append(request, role="assistant", content=reply, meta=meta or {})

    @staticmethod
    def _append(request: NormalizedRequest, role: str, content: str, meta: Dict[str, Any]) -> bool:
        from capabilities.base.capability_context import CapabilityContext
        from capabilities.resolver import CapabilityResolver

        result = CapabilityResolver.execute(
            "conversation_memory",
            "append",
            {
                "conversation_id": request.conversation_id,
                "role": role,
                "content": content,
                "channel": request.channel,
                "actor": request.role,
                "title": request.sender_name if request.role == "customer" else "",
                "contact_ref": request.actor_ref,
                "meta": meta,
            },
            CapabilityContext(module_id="runtime", correlation_id=request.request_id),
        )
        return bool(result.success)

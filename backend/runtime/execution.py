"""B.O.S. Execution Engine v1.0

Stage 8 of Runtime Lifecycle: Executes policy-approved steps through the Capability Resolver.
Steps may reference earlier outputs with "{{steps.N.path}}".
"""

import re
from typing import Any, Dict, List, Optional

from .contracts import (
    CapabilitySelection,
    ExecutionPlan,
    ExecutionResult,
    NormalizedRequest,
    PolicyDecision,
    RuntimeContext,
)

# Protocol parsing of the platform's own step-reference syntax (not natural language).
_STEP_REF = re.compile(r"\{\{\s*steps\.(\d+)\.([A-Za-z0-9_.]+)\s*\}\}")


class ExecutionEngine:
    """Executes approved platform capabilities and records each step's result."""

    @staticmethod
    def execute_plan(
        request: NormalizedRequest,
        plan: ExecutionPlan,
        policy: PolicyDecision,
        capabilities: CapabilitySelection,
        context: RuntimeContext,
        only_step_ids: Optional[List[Any]] = None,
        previous: Optional[List[Dict[str, Any]]] = None,
    ) -> ExecutionResult:
        from capabilities.base.capability_context import CapabilityContext
        from capabilities.resolver import CapabilityResolver

        results: Dict[str, Dict[str, Any]] = {str(r["step_id"]): r for r in (previous or [])}
        for step in policy.allowed_steps:
            if only_step_ids is not None and step.step_id not in only_step_ids:
                continue
            params = ExecutionEngine._resolve_refs(step.params, results)
            ctx = CapabilityContext(
                module_id="runtime",
                correlation_id=f"{request.request_id}:{step.step_id}",
                extra={"role": request.role, "channel": request.channel, "conversation_id": request.conversation_id},
            )
            outcome = CapabilityResolver.execute(step.capability, step.action, params, ctx)
            results[str(step.step_id)] = {
                "step_id": step.step_id,
                "capability": step.capability,
                "action": step.action,
                "title": step.title,
                "risk": step.risk,
                "params": params,
                "success": bool(outcome.success and (outcome.data or {}).get("success", True)),
                "data": outcome.data or {},
                "error": outcome.error or (outcome.data or {}).get("error"),
            }
            if not results[str(step.step_id)]["success"] and not step.continue_on_failure:
                break

        ordered = sorted(results.values(), key=lambda r: int(r["step_id"]))
        succeeded = sum(1 for r in ordered if r["success"])
        return ExecutionResult(
            success=all(r["success"] for r in ordered),
            action_type="PLAN_EXECUTED" if ordered else "REPLY_ONLY",
            factual_packet={"executed": succeeded, "failed": len(ordered) - succeeded},
            step_results=ordered,
        )

    @staticmethod
    def _resolve_refs(value: Any, results: Dict[str, Dict[str, Any]]) -> Any:
        if isinstance(value, dict):
            return {k: ExecutionEngine._resolve_refs(v, results) for k, v in value.items()}
        if isinstance(value, list):
            return [ExecutionEngine._resolve_refs(v, results) for v in value]
        if not isinstance(value, str) or "{{" not in value:
            return value

        def lookup(step_id: str, path: str) -> Any:
            node: Any = (results.get(step_id) or {}).get("data", {})
            for part in path.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            return node

        whole = _STEP_REF.fullmatch(value.strip())
        if whole:
            return lookup(whole.group(1), whole.group(2))
        return _STEP_REF.sub(lambda m: str(lookup(m.group(1), m.group(2)) or ""), value)

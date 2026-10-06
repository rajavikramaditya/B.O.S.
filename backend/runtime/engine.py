"""B.O.S. Runtime Engine v1.0 (Workflow Graph Architecture)

Central state machine that drives every request through the 11-stage lifecycle:

    Observe → Context → Understand → Reason → Plan → Policy → (Approval) →
    Capability → Execute → Verify (→ Retry) → Memory → Response

Each stage runs exactly once per pass; results are carried between nodes in a
run record, so side-effecting steps are never executed twice by accident.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .capability import CapabilityEngine
from .context import ContextEngine
from .contracts import (
    ActorRole,
    BusinessIntent,
    CapabilitySelection,
    ExecutionPlan,
    ExecutionResult,
    NormalizedRequest,
    PolicyDecision,
    RuntimeContext,
    RuntimeResponse,
    VerificationReport,
)
from .execution import ExecutionEngine
from .graph import NodeType
from .memory import MemoryEngine
from .observation import ObservationEngine
from .planner import GraphPlanner
from .planning import PlanningEngine
from .policy import PolicyEngine
from .reasoning import ReasoningEngine
from .response import ResponseEngine
from .state import RuntimeState
from .understanding import UnderstandingEngine
from .verification import VerificationEngine

STEP_RETRY_LIMIT = 2  # RETRY node increments first, so 2 allows exactly one retry.


@dataclass
class _Run:
    """Stage outputs for one pass through the graph."""

    request: NormalizedRequest
    preapproved: bool = False
    context: RuntimeContext = field(default_factory=RuntimeContext)
    intent: BusinessIntent = field(default_factory=BusinessIntent)
    strategy: Any = None
    plan: Optional[ExecutionPlan] = None
    policy: PolicyDecision = field(default_factory=PolicyDecision)
    selection: CapabilitySelection = field(default_factory=CapabilitySelection)
    execution: ExecutionResult = field(default_factory=ExecutionResult)
    verification: VerificationReport = field(default_factory=VerificationReport)
    response: Optional[RuntimeResponse] = None


class BOSRuntimeEngine:
    """Workflow State Graph Execution Engine for Business Operating System."""

    @classmethod
    def execute(
        cls,
        *,
        role: ActorRole | str = "customer",
        message: str = "",
        selected_model: str = "auto",
        sender_name: str = "ji",
        phone: str = "",
        channel: str = "command_center",
        raw_payload: Dict[str, Any] | None = None,
        existing_state: Optional[RuntimeState] = None,
        conversation_id: str = "",
        actor_ref: str = "",
        preapproved: bool = False,
    ) -> Dict[str, Any]:
        state = existing_state or RuntimeState()
        state.status = "RUNNING"
        state.max_retries = STEP_RETRY_LIMIT

        request = ObservationEngine.observe(
            role=role,
            message=message,
            selected_model=selected_model,
            sender_name=sender_name,
            phone=phone,
            channel=channel,
            raw_payload=raw_payload,
            conversation_id=conversation_id,
            actor_ref=actor_ref,
        )
        state.request_data = asdict(request)
        run = _Run(request=request, preapproved=preapproved)

        graph = GraphPlanner.build_workflow_graph(request, run.intent, run.context)
        node_id = "OBSERVE"
        guard = 0
        while node_id and node_id != "END" and guard < 40:
            guard += 1
            state.transition_to(node_id)
            node = graph.nodes.get(node_id)
            if node is None:
                break
            try:
                cls._execute_node(node.node_type, state, run)
            except Exception as ex:  # a stage must never take the platform down
                state.record_error(f"{node_id}: {ex}", node_id)
                state.status = "FAILED"
                break
            next_id = graph.get_next_node(node_id, state)
            if not next_id or next_id == node_id:
                break
            node_id = next_id

        if run.response is None:
            cls._execute_node(NodeType.RESPONSE, state, run)

        if state.status != "FAILED":
            state.status = "WAITING_APPROVAL" if run.policy.pending_steps and not run.execution.step_results else "COMPLETED"
        state.transition_to("END", status=state.status)
        return cls._result(state, run)

    @classmethod
    def _execute_node(cls, ntype: NodeType, state: RuntimeState, run: _Run) -> None:
        req = run.request
        if ntype == NodeType.CONTEXT:
            run.context = ContextEngine.load_context(req)
            state.memory_context = {
                "history_messages": len(run.context.conversation_history),
                "capabilities": [c["capability"] for c in run.context.capability_catalog],
                "autopilot_mode": run.context.autopilot_mode,
            }

        elif ntype == NodeType.UNDERSTAND:
            run.intent = UnderstandingEngine.understand(req, run.context)
            state.intent_data = asdict(run.intent)

        elif ntype == NodeType.REASON:
            run.strategy = ReasoningEngine.reason(run.intent, run.context)
            state.plan_data["strategy"] = getattr(run.strategy, "__dict__", {})

        elif ntype == NodeType.PLAN:
            run.plan = PlanningEngine.create_plan(run.intent, run.strategy)
            run.plan.preapproved = run.preapproved
            state.plan_data["plan"] = asdict(run.plan)

        elif ntype == NodeType.POLICY:
            run.policy = PolicyEngine.validate_policy(
                run.plan, run.context, role=req.role, raw_text=req.message, actor_ref=req.actor_ref
            )
            state.policy_data = {
                "status": run.policy.status,
                "reason": run.policy.reason,
                "requires_confirmation": run.policy.requires_confirmation,
                "pending": [s.step_id for s in run.policy.pending_steps],
                "denied": run.policy.denied_steps,
            }

        elif ntype == NodeType.APPROVAL:
            # Held steps are handed back to the caller as approval requests; allowed steps continue.
            state.pending_action = ",".join(str(s.step_id) for s in run.policy.pending_steps) or None

        elif ntype == NodeType.CAPABILITY_SELECT:
            run.selection = CapabilityEngine.select_capabilities(run.plan, run.policy)
            state.plan_data["capabilities"] = asdict(run.selection)

        elif ntype == NodeType.EXECUTE:
            retry_ids = run.verification.retryable_steps if run.execution.step_results else None
            run.execution = ExecutionEngine.execute_plan(
                req,
                run.plan,
                run.policy,
                run.selection,
                run.context,
                only_step_ids=retry_ids,
                previous=run.execution.step_results,
            )
            state.execution_data = asdict(run.execution)

        elif ntype == NodeType.VERIFY:
            run.verification = VerificationEngine.verify(req, run.execution)
            # Only safe-to-repeat failures may loop back through RETRY.
            state.verification_data = {
                "verified": run.verification.verified or not run.verification.retryable_steps,
                "truth_level": run.verification.truth_level,
                "notes": run.verification.notes,
            }

        elif ntype == NodeType.RETRY:
            state.retry_count += 1

        elif ntype == NodeType.MEMORY:
            update = MemoryEngine.update_memory(req, run.verification, run.context, run.execution.step_results)
            state.memory_context["update"] = asdict(update)

        elif ntype == NodeType.RESPONSE:
            run.response = ResponseEngine.generate_response(
                req, run.verification, run.execution, run.intent, run.policy, run.context
            )
            state.response_data = asdict(run.response)
            MemoryEngine.remember_reply(req, run.response.reply, {"truth": run.verification.truth_level})

    @staticmethod
    def _result(state: RuntimeState, run: _Run) -> Dict[str, Any]:
        intent = run.intent
        response = run.response or RuntimeResponse(reply="", action_type="UNKNOWN", factual_packet={})
        return {
            "reply": response.reply,
            "action_type": response.action_type,
            "factual_packet": response.factual_packet,
            "role": run.request.role,
            "source": "bos_runtime",
            "execution_id": state.execution_id,
            "workflow_status": state.status,
            "conversation_id": run.request.conversation_id,
            "request_id": run.request.request_id,
            "ai_available": not (intent.error or "").startswith("ai_unavailable"),
            "intent": {
                "type": intent.intent_type,
                "goal": intent.goal,
                "summary": intent.summary,
                "language": intent.language,
                "confidence": intent.confidence,
                "entities": intent.entities,
            },
            "executed_steps": run.execution.step_results,
            "pending_steps": [
                {
                    "step_id": s.step_id,
                    "capability": s.capability,
                    "action": s.action,
                    "params": s.params,
                    "title": s.title,
                    "reason": s.reason,
                    "risk": s.risk,
                }
                for s in run.policy.pending_steps
            ],
            "denied_steps": run.policy.denied_steps,
            "insights": intent.insights,
            "truth_level": run.verification.truth_level,
            "errors": state.errors,
            "trace": [h.node for h in state.execution_history],
        }


def process_message(
    *,
    role: ActorRole | str = "customer",
    message: str,
    selected_model: str = "auto",
    sender_name: str = "ji",
    phone: str = "",
    channel: str = "command_center",
    conversation_id: str = "",
    actor_ref: str = "",
) -> Dict[str, Any]:
    """Unified entry point routing all interactions through BOSRuntimeEngine."""
    return BOSRuntimeEngine.execute(
        role=role,
        message=message,
        selected_model=selected_model,
        sender_name=sender_name,
        phone=phone,
        channel=channel,
        conversation_id=conversation_id,
        actor_ref=actor_ref,
    )

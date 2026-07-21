"""B.O.S. Runtime Engine v0.1 (Workflow Graph Architecture)

Central state machine orchestrator executing state graph workflows.
Supports linear, branching, approval-paused, retry, and recoverable workflows.
"""

from typing import Any, Dict, Optional
from .state import RuntimeState, WorkflowStatus
from .graph import WorkflowGraph, NodeType
from .planner import GraphPlanner
from .observation import ObservationEngine
from .understanding import UnderstandingEngine
from .context import ContextEngine
from .reasoning import ReasoningEngine
from .planning import PlanningEngine
from .policy import PolicyEngine
from .capability import CapabilityEngine
from .execution import ExecutionEngine
from .verification import VerificationEngine
from .memory import MemoryEngine
from .response import ResponseEngine
from .contracts import ActorRole


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
    ) -> Dict[str, Any]:
        state = existing_state or RuntimeState()
        state.status = "RUNNING"

        # Initialize request
        norm_req = ObservationEngine.observe(
            role=role,
            message=message,
            selected_model=selected_model,
            sender_name=sender_name,
            phone=phone,
            channel=channel,
            raw_payload=raw_payload,
        )
        state.request_data = norm_req.__dict__

        # Stage 2: Understand
        intent = UnderstandingEngine.understand(norm_req)
        state.intent_data = intent.__dict__

        # Stage 3: Load Context
        ctx = ContextEngine.load_context(norm_req, intent)
        state.memory_context = ctx.__dict__

        # Stage 4 & 5: Build Workflow Graph Plan
        graph = GraphPlanner.build_workflow_graph(norm_req, intent, ctx)
        state.save_checkpoint("initial_plan")

        # Execute Graph State Machine
        current_node_id = "OBSERVE"
        state.current_node = current_node_id

        while current_node_id and current_node_id != "END":
            state.transition_to(current_node_id)
            node = graph.nodes.get(current_node_id)
            if not node:
                break

            # Process node execution logic
            cls._execute_node(node, state, norm_req, intent, ctx)

            # Check if workflow reached a paused/waiting state
            if state.status in ("PAUSED", "WAITING_APPROVAL"):
                state.save_checkpoint("approval_paused")
                break

            next_node_id = graph.get_next_node(current_node_id, state)
            if not next_node_id or next_node_id == current_node_id:
                break
            current_node_id = next_node_id

        if state.status not in ("PAUSED", "WAITING_APPROVAL"):
            state.status = "COMPLETED"
            state.transition_to("END", status="COMPLETED")

        out = state.execution_data.get("raw_result") if isinstance(state.execution_data.get("raw_result"), dict) else {}
        out["reply"] = state.response_data.get("reply") or state.execution_data.get("reply", "")
        out["action_type"] = state.response_data.get("action_type") or state.execution_data.get("action_type", "UNKNOWN")
        out["factual_packet"] = state.response_data.get("factual_packet") or state.execution_data.get("factual_packet", {})
        out.setdefault("role", norm_req.role)
        out["source"] = "bos_runtime"
        out["execution_id"] = state.execution_id
        out["workflow_status"] = state.status
        return out

    @classmethod
    def _execute_node(cls, node, state, norm_req, intent, ctx):
        ntype = node.node_type

        if ntype == NodeType.REASON:
            strategy = ReasoningEngine.reason(intent, ctx)
            state.plan_data["strategy"] = strategy.__dict__

        elif ntype == NodeType.PLAN:
            plan = PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))
            state.plan_data["plan"] = plan.__dict__

        elif ntype == NodeType.POLICY:
            plan = PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))
            pdecision = PolicyEngine.validate_policy(plan, ctx)
            state.policy_data = pdecision.__dict__
            if pdecision.requires_confirmation:
                state.status = "WAITING_APPROVAL"

        elif ntype == NodeType.APPROVAL:
            # Human approval check
            if state.policy_data.get("requires_confirmation"):
                state.status = "WAITING_APPROVAL"

        elif ntype == NodeType.CAPABILITY_SELECT:
            plan = PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))
            caps = CapabilityEngine.select_capabilities(plan)
            state.plan_data["capabilities"] = caps.__dict__

        elif ntype == NodeType.EXECUTE:
            plan = PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))
            pdecision = PolicyEngine.validate_policy(plan, ctx)
            caps = CapabilityEngine.select_capabilities(plan)
            exec_res = ExecutionEngine.execute_plan(norm_req, plan, pdecision, caps, ctx)
            state.execution_data = exec_res.__dict__

        elif ntype == NodeType.VERIFY:
            exec_res = ExecutionEngine.execute_plan(
                norm_req,
                PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)),
                PolicyEngine.validate_policy(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)), ctx),
                CapabilityEngine.select_capabilities(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))),
                ctx,
            )
            vreport = VerificationEngine.verify(norm_req, exec_res)
            state.verification_data = vreport.__dict__

        elif ntype == NodeType.RETRY:
            state.retry_count += 1

        elif ntype == NodeType.MEMORY:
            exec_res = ExecutionEngine.execute_plan(
                norm_req,
                PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)),
                PolicyEngine.validate_policy(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)), ctx),
                CapabilityEngine.select_capabilities(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))),
                ctx,
            )
            vreport = VerificationEngine.verify(norm_req, exec_res)
            mupdate = MemoryEngine.update_memory(norm_req, vreport, ctx)
            state.memory_context["update"] = mupdate.__dict__

        elif ntype == NodeType.RESPONSE:
            exec_res = ExecutionEngine.execute_plan(
                norm_req,
                PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)),
                PolicyEngine.validate_policy(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx)), ctx),
                CapabilityEngine.select_capabilities(PlanningEngine.create_plan(intent, ReasoningEngine.reason(intent, ctx))),
                ctx,
            )
            vreport = VerificationEngine.verify(norm_req, exec_res)
            resp = ResponseEngine.generate_response(norm_req, vreport, exec_res)
            state.response_data = resp.__dict__


def process_message(
    *,
    role: ActorRole | str = "customer",
    message: str,
    selected_model: str = "auto",
    sender_name: str = "ji",
    phone: str = "",
    channel: str = "command_center",
) -> Dict[str, Any]:
    """Unified entry point routing all interactions through BOSRuntimeEngine."""
    return BOSRuntimeEngine.execute(
        role=role,
        message=message,
        selected_model=selected_model,
        sender_name=sender_name,
        phone=phone,
        channel=channel,
    )

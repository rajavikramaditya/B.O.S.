from __future__ import annotations

from typing import Any, TypedDict


SCHEMA_VERSION = "1.0.0"


class ManagerActionPacket(TypedDict):
    schema_version: str
    intent: str | None
    confidence: float
    route_type: str | None
    tool: str | None
    tool_args: dict[str, Any]
    risk_level: str
    needs_approval: bool
    protected_action: str | None
    next_safe_action: str | None
    is_followup: bool
    followup_type: str | None
    refers_to_pending_action: bool
    approval_strength: str | None
    raw_model: Any
    provenance: dict[str, Any]


class PolicyDecisionPacket(TypedDict):
    schema_version: str
    policy_decision: str
    action_type: str | None
    blocked_reason: str | None
    response_goal: str
    executable_tool: str | None
    requires_owner_approval: bool
    approval_reason: str | None
    memory_save_status: str | None
    evidence_required: bool
    tool_allowed: bool
    notes: list[str]


class ToolExecutionPacket(TypedDict):
    schema_version: str
    tool_name: str | None
    tool_executed: bool
    tool_result_present: bool
    status: str
    result: Any
    error: str | None
    side_effects: list[str]
    read_only: bool
    source: str | None
    evidence_summary: str | None


class TracePacket(TypedDict, total=False):
    schema_version: str
    selected_model: str | None
    actual_model: str | None
    candidate_models: list[str]
    intent_model_call_count: int
    response_model_call_count: int
    total_model_call_count: int
    fallback_model_used: bool
    model_unavailable_reason: str | None
    tool_suggested: str | None
    tool_executed: bool
    tool_result_present: bool
    executed_tool_name: str | None
    memory_save_status: str | None
    timing: dict[str, Any]
    execution_steps: list[dict[str, Any]]
    existing_trace_fields: dict[str, Any]


class MemoryContextPacket(TypedDict):
    schema_version: str
    memory_mode: str
    short_context_used: bool
    memory_search_used: str
    memory_hits_count: int
    hits: list[dict[str, Any]]
    context_text: str
    source: str
    confidence: float
    expires_at: str | None
    retrieval_status: str


class MemoryWriteDecisionPacket(TypedDict):
    schema_version: str
    should_save: bool
    memory_type: str | None
    content: str | None
    reason: str | None
    owner_confirmation_required: bool
    owner_confirmed: bool
    retention: str
    sensitivity_level: str
    source_message: str | None
    expires_at: str | None
    blocked_reason: str | None


class FinalResponsePacket(TypedDict):
    schema_version: str
    reply: str
    route_type: str | None
    final_reply_source: str | None
    action_packet: ManagerActionPacket | dict[str, Any] | None
    policy_decision: PolicyDecisionPacket | dict[str, Any] | None
    tool_execution: ToolExecutionPacket | dict[str, Any] | None
    memory_context: MemoryContextPacket | dict[str, Any] | None
    memory_write_decision: MemoryWriteDecisionPacket | dict[str, Any] | None
    trace: TracePacket | dict[str, Any] | None
    artifacts: list[dict[str, Any]]
    side_effects: list[str]
    warnings: list[str]


def make_manager_action_packet(
    intent: str | None = None,
    confidence: float = 0.0,
    route_type: str | None = None,
    tool: str | None = None,
    tool_args: dict[str, Any] | None = None,
    risk_level: str = "low",
    needs_approval: bool = False,
    protected_action: str | None = None,
    next_safe_action: str | None = None,
    is_followup: bool = False,
    followup_type: str | None = None,
    refers_to_pending_action: bool = False,
    approval_strength: str | None = None,
    raw_model: Any = None,
    provenance: dict[str, Any] | None = None,
) -> ManagerActionPacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "intent": intent,
        "confidence": float(confidence),
        "route_type": route_type,
        "tool": tool,
        "tool_args": dict(tool_args or {}),
        "risk_level": risk_level,
        "needs_approval": bool(needs_approval),
        "protected_action": protected_action,
        "next_safe_action": next_safe_action,
        "is_followup": bool(is_followup),
        "followup_type": followup_type,
        "refers_to_pending_action": bool(refers_to_pending_action),
        "approval_strength": approval_strength,
        "raw_model": raw_model,
        "provenance": dict(provenance or {}),
    }


def make_policy_decision_packet(
    policy_decision: str = "manager_response_no_tool",
    action_type: str | None = None,
    blocked_reason: str | None = None,
    response_goal: str = "",
    executable_tool: str | None = None,
    requires_owner_approval: bool = False,
    approval_reason: str | None = None,
    memory_save_status: str | None = None,
    evidence_required: bool = False,
    tool_allowed: bool = False,
    notes: list[str] | None = None,
) -> PolicyDecisionPacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_decision": policy_decision,
        "action_type": action_type,
        "blocked_reason": blocked_reason,
        "response_goal": response_goal,
        "executable_tool": executable_tool,
        "requires_owner_approval": bool(requires_owner_approval),
        "approval_reason": approval_reason,
        "memory_save_status": memory_save_status,
        "evidence_required": bool(evidence_required),
        "tool_allowed": bool(tool_allowed),
        "notes": list(notes or []),
    }


def make_tool_execution_packet(
    tool_name: str | None = None,
    tool_executed: bool = False,
    tool_result_present: bool = False,
    status: str = "not_executed",
    result: Any = None,
    error: str | None = None,
    side_effects: list[str] | None = None,
    read_only: bool = True,
    source: str | None = None,
    evidence_summary: str | None = None,
) -> ToolExecutionPacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_name": tool_name,
        "tool_executed": bool(tool_executed),
        "tool_result_present": bool(tool_result_present),
        "status": status,
        "result": result,
        "error": error,
        "side_effects": list(side_effects or []),
        "read_only": bool(read_only),
        "source": source,
        "evidence_summary": evidence_summary,
    }


def make_memory_context_packet(
    memory_mode: str = "short_term_only",
    short_context_used: bool = False,
    memory_search_used: str = "none",
    memory_hits_count: int = 0,
    hits: list[dict[str, Any]] | None = None,
    context_text: str = "",
    source: str = "none",
    confidence: float = 0.0,
    expires_at: str | None = None,
    retrieval_status: str = "not_used",
) -> MemoryContextPacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "memory_mode": memory_mode,
        "short_context_used": bool(short_context_used),
        "memory_search_used": memory_search_used,
        "memory_hits_count": int(memory_hits_count),
        "hits": list(hits or []),
        "context_text": context_text,
        "source": source,
        "confidence": float(confidence),
        "expires_at": expires_at,
        "retrieval_status": retrieval_status,
    }


def make_memory_write_decision_packet(
    should_save: bool = False,
    memory_type: str | None = None,
    content: str | None = None,
    reason: str | None = None,
    owner_confirmation_required: bool = False,
    owner_confirmed: bool = False,
    retention: str = "short_term",
    sensitivity_level: str = "normal",
    source_message: str | None = None,
    expires_at: str | None = None,
    blocked_reason: str | None = None,
) -> MemoryWriteDecisionPacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "should_save": bool(should_save),
        "memory_type": memory_type,
        "content": content,
        "reason": reason,
        "owner_confirmation_required": bool(owner_confirmation_required),
        "owner_confirmed": bool(owner_confirmed),
        "retention": retention,
        "sensitivity_level": sensitivity_level,
        "source_message": source_message,
        "expires_at": expires_at,
        "blocked_reason": blocked_reason,
    }


def make_final_response_packet(
    reply: str = "",
    route_type: str | None = None,
    final_reply_source: str | None = None,
    action_packet: ManagerActionPacket | dict[str, Any] | None = None,
    policy_decision: PolicyDecisionPacket | dict[str, Any] | None = None,
    tool_execution: ToolExecutionPacket | dict[str, Any] | None = None,
    memory_context: MemoryContextPacket | dict[str, Any] | None = None,
    memory_write_decision: MemoryWriteDecisionPacket | dict[str, Any] | None = None,
    trace: TracePacket | dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    side_effects: list[str] | None = None,
    warnings: list[str] | None = None,
) -> FinalResponsePacket:
    return {
        "schema_version": SCHEMA_VERSION,
        "reply": reply,
        "route_type": route_type,
        "final_reply_source": final_reply_source,
        "action_packet": action_packet,
        "policy_decision": policy_decision,
        "tool_execution": tool_execution,
        "memory_context": memory_context,
        "memory_write_decision": memory_write_decision,
        "trace": trace,
        "artifacts": list(artifacts or []),
        "side_effects": list(side_effects or []),
        "warnings": list(warnings or []),
    }


__all__ = [
    "SCHEMA_VERSION",
    "ManagerActionPacket",
    "PolicyDecisionPacket",
    "ToolExecutionPacket",
    "TracePacket",
    "MemoryContextPacket",
    "MemoryWriteDecisionPacket",
    "FinalResponsePacket",
    "make_manager_action_packet",
    "make_policy_decision_packet",
    "make_tool_execution_packet",
    "make_memory_context_packet",
    "make_memory_write_decision_packet",
    "make_final_response_packet",
]

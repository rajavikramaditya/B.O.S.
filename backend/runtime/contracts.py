"""B.O.S. Runtime Contracts v0.1

Defines immutable input/output structures for every stage of the
Runtime lifecycle:
Observe -> Understand -> Load Context -> Reason -> Plan -> Policy -> Capability -> Execute -> Verify -> Memory -> Response
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


ActorRole = Literal["owner", "customer", "employee", "system"]


@dataclass
class NormalizedRequest:
    """Stage 1: Observation Engine output."""
    request_id: str
    role: ActorRole
    message: str
    channel: str = "command_center"
    selected_model: str = "auto"
    sender_name: str = "ji"
    phone: str = ""
    timestamp: float = 0.0
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""
    actor_ref: str = ""
    # Capabilities the caller may use ("cap" = all actions, "cap:read" = read actions only).
    # None means unrestricted (owner, platform). Set from API key scopes by the interface.
    grants: Optional[List[str]] = None


@dataclass
class BusinessIntent:
    """Stage 2: Understanding Engine output."""
    intent_type: str = "unknown"
    action: str = "unknown"
    entities: Dict[str, Any] = field(default_factory=dict)
    goal: str = ""
    slots: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    summary: str = ""
    language: str = ""
    proposed_steps: List[Dict[str, Any]] = field(default_factory=list)
    reply_draft: str = ""
    insights: List[Dict[str, Any]] = field(default_factory=list)
    understood_by: str = ""
    error: Optional[str] = None


@dataclass
class RuntimeContext:
    """Stage 3: Context Engine output."""
    memory_packet: Dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""
    live_snapshot: Dict[str, Any] = field(default_factory=dict)
    owner_preferences: Dict[str, Any] = field(default_factory=dict)
    system_knowledge: Dict[str, Any] = field(default_factory=dict)
    entity_recency_cache: Dict[str, str] = field(default_factory=dict)
    business_profile: Dict[str, Any] = field(default_factory=dict)
    business_snapshot: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    capability_catalog: List[Dict[str, Any]] = field(default_factory=list)
    actor_profile: Dict[str, Any] = field(default_factory=dict)
    autopilot_mode: str = "autopilot"



@dataclass
class ReasoningStrategy:
    """Stage 4: Reasoning Engine output."""
    strategy_type: str = "direct"
    reasoning_notes: str = ""
    target_capabilities: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlanStep:
    step_id: Any
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    capability: str = "default"
    continue_on_failure: bool = False
    title: str = ""
    reason: str = ""
    risk: str = "safe"



PlanStep = ExecutionPlanStep


@dataclass
class ExecutionPlan:
    """Stage 5: Planning Engine output."""
    plan_id: str
    intent_type: str
    steps: List[ExecutionPlanStep] = field(default_factory=list)
    requires_approval: bool = False
    goal: str = ""
    preapproved: bool = False


@dataclass
class PolicyDecision:
    """Stage 6: Policy Engine output."""
    status: str = "ALLOW"
    action: str = "none"
    reason: str = ""
    protected: bool = False
    requires_confirmation: bool = False
    allowed_steps: List[Any] = field(default_factory=list)
    pending_steps: List[Any] = field(default_factory=list)
    denied_steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CapabilitySelection:
    """Stage 7: Capability Engine output."""
    selected_capabilities: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    mappings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Stage 8: Execution Engine output."""
    success: bool = True
    action_type: str = "UNKNOWN"
    reply: str = ""
    factual_packet: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    raw_result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    """Stage 9: Verification Engine output."""
    verified: bool = True
    truth_level: str = "verified"
    notes: str = ""
    scrubbed_reply: str = ""
    factual_packet: Dict[str, Any] = field(default_factory=dict)
    action_type: str = ""
    failed_steps: List[Dict[str, Any]] = field(default_factory=list)
    retryable_steps: List[Any] = field(default_factory=list)


@dataclass
class MemoryUpdateReport:
    """Stage 10: Memory Engine output."""
    saved: bool = True
    memory_key: str = ""
    persisted: bool = True
    autosaved_facts: List[Any] = field(default_factory=list)


MemoryUpdate = MemoryUpdateReport


@dataclass
class RuntimeResponse:
    """Stage 11: Response Engine output."""
    reply: str
    action_type: str
    factual_packet: Dict[str, Any]
    source: str = "bos_runtime"
    execution_id: str = ""
    route: str = "runtime"
    role: str = ""
    trace: Dict[str, Any] = field(default_factory=dict)

"""B.O.S. Runtime Contracts v0.1

Defines immutable input/output structures for every stage of the
Runtime lifecycle:
Observe -> Understand -> Load Context -> Reason -> Plan -> Policy -> Capability -> Execute -> Verify -> Memory -> Response
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


ActorRole = Literal["owner", "customer", "employee"]


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


@dataclass
class BusinessIntent:
    """Stage 2: Understanding Engine output."""
    intent_type: str = "unknown"
    action: str = "unknown"
    entities: Dict[str, Any] = field(default_factory=dict)
    goal: str = ""
    slots: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class RuntimeContext:
    """Stage 3: Context Engine output."""
    memory_packet: Dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""
    live_snapshot: Dict[str, Any] = field(default_factory=dict)
    owner_preferences: Dict[str, Any] = field(default_factory=dict)
    system_knowledge: Dict[str, Any] = field(default_factory=dict)


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


PlanStep = ExecutionPlanStep


@dataclass
class ExecutionPlan:
    """Stage 5: Planning Engine output."""
    plan_id: str
    intent_type: str
    steps: List[ExecutionPlanStep] = field(default_factory=list)
    requires_approval: bool = False


@dataclass
class PolicyDecision:
    """Stage 6: Policy Engine output."""
    status: str = "ALLOW"
    action: str = "none"
    reason: str = ""
    protected: bool = False
    requires_confirmation: bool = False


@dataclass
class CapabilitySelection:
    """Stage 7: Capability Engine output."""
    selected_capabilities: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Stage 8: Execution Engine output."""
    success: bool = True
    action_type: str = "UNKNOWN"
    reply: str = ""
    factual_packet: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class VerificationReport:
    """Stage 9: Verification Engine output."""
    verified: bool = True
    truth_level: str = "verified"
    notes: str = ""


@dataclass
class MemoryUpdateReport:
    """Stage 10: Memory Engine output."""
    saved: bool = True
    memory_key: str = ""


MemoryUpdate = MemoryUpdateReport


@dataclass
class RuntimeResponse:
    """Stage 11: Response Engine output."""
    reply: str
    action_type: str
    factual_packet: Dict[str, Any]
    source: str = "bos_runtime"
    execution_id: str = ""

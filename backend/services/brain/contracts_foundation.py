"""M0 foundation Contracts for Orai Radio Neena system."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# Option B actor roles (human channel). Not LLM model roles.
ActorRole = Literal["owner", "customer", "employee"]


class ErrorResponse(BaseModel):
    """Standard unified error response structure (AGENTS rule 6).

    Mandated fields: error_code, message, details, recoverable, next_action.
    `ok` and `timestamp` are always-present envelope extras.
    """
    ok: bool = False
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None
    recoverable: bool = False
    next_action: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class SafetyDecision(BaseModel):
    """Structured safety check decision packet."""
    action: str
    reclassified: bool
    original_action: str
    reason: Optional[str] = None


class OwnerCommand(BaseModel):
    """Structured request representation of owner natural language inputs."""
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class InterpreterPacket(BaseModel):
    """Structured representation of output from NLP classification step."""
    action: str
    confidence: float
    slots: dict[str, Any] = Field(default_factory=dict)
    needs_confirmation: bool = False
    owner_facing_summary: str = ""


class CapsuleSafetyState(BaseModel):
    """Safety state snapshot for single broadcast capsule verification."""
    capsule_id: int
    audio_truth_level: str
    db_broadcast_ready: bool
    azuracast_status: str
    is_ready_for_broadcast: bool


__all__ = [
    "ActorRole",
    "CapsuleSafetyState",
    "ErrorResponse",
    "InterpreterPacket",
    "OwnerCommand",
    "SafetyDecision",
]

from __future__ import annotations

from typing import Any, TypedDict

from services.brain.contracts import (
    MemoryWriteDecisionPacket,
    make_memory_write_decision_packet,
)


ALLOWED_PERMANENT_MEMORY_TYPES = {
    "owner_style_preference",
    "station_identity",
    "station_policy",
    "content_tone_rule",
    "operational_preference",
    "approved_workflow_rule",
    # Phase A/B/C — Neena self notebook (identity + personality + life + mind architecture)
    "neena_self_identity",
    "neena_personality_profile",
    "neena_life_episode",
    "neena_mind_architecture",
    "neena_day_summary",
    "neena_week_summary",
    "neena_future_intention",
}

# Customer 1B — auto-salient only (never owner policy / tools).
ALLOWED_CUSTOMER_SALIENT_TYPES = {
    "customer_name",
    "listener_preference",
    "callback_request",
    "complaint_topic",
    "show_interest",
}

TEMPORARY_MEMORY_TYPES = {
    "temporary_command",
    "one_turn_context",
    "pending_action",
    "diagnostic_result",
    "tool_result",
    "draft_content",
}

OWNER_CONFIRMATION_REQUIRED_TYPES = set(ALLOWED_PERMANENT_MEMORY_TYPES)

MEMORY_SAFETY_CATEGORIES = {
    "normal",
    "sensitive",
    "restricted",
    "secret",
}

BLOCKED_SENSITIVITY_LEVELS = {
    "restricted",
    "secret",
}


class MemoryCandidateClassification(TypedDict):
    memory_type: str
    content: str
    source_message: str | None
    should_save: bool
    owner_confirmation_required: bool
    owner_confirmed: bool
    retention: str
    sensitivity_level: str
    reason: str
    expires_at: str | None
    blocked_reason: str | None
    metadata: dict[str, Any]


def classify_memory_candidate(
    content: str,
    memory_type: str | None = None,
    source_message: str | None = None,
    owner_confirmed: bool = False,
    retention: str | None = None,
    sensitivity_level: str = "normal",
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> MemoryCandidateClassification:
    """
    Dry-run classifier for future permanent memory candidates.

    Example: an owner style preference such as "RJ scripts Bundeli comedy tone me
    rakha karo" can be classified as `owner_style_preference`, but it still needs
    explicit owner confirmation before permanent save.

    Example: a temporary command such as "diagnostics run karo" should be
    classified as `temporary_command` and must not become permanent memory.
    """
    normalized_type = (memory_type or "unknown").strip().lower()
    normalized_sensitivity = (sensitivity_level or "normal").strip().lower()
    if normalized_sensitivity not in MEMORY_SAFETY_CATEGORIES:
        normalized_sensitivity = "sensitive"

    clean_content = (content or "").strip()
    clean_metadata = dict(metadata or {})

    if not clean_content:
        return {
            "memory_type": normalized_type,
            "content": clean_content,
            "source_message": source_message,
            "should_save": False,
            "owner_confirmation_required": False,
            "owner_confirmed": bool(owner_confirmed),
            "retention": retention or "blocked",
            "sensitivity_level": normalized_sensitivity,
            "reason": "Empty content cannot be saved as memory.",
            "expires_at": expires_at,
            "blocked_reason": "empty_content",
            "metadata": clean_metadata,
        }

    if normalized_sensitivity in BLOCKED_SENSITIVITY_LEVELS:
        return {
            "memory_type": normalized_type,
            "content": clean_content,
            "source_message": source_message,
            "should_save": False,
            "owner_confirmation_required": True,
            "owner_confirmed": bool(owner_confirmed),
            "retention": retention or "blocked",
            "sensitivity_level": normalized_sensitivity,
            "reason": "Restricted or secret content is blocked from permanent memory.",
            "expires_at": expires_at,
            "blocked_reason": f"{normalized_sensitivity}_content_blocked",
            "metadata": clean_metadata,
        }

    if normalized_type in TEMPORARY_MEMORY_TYPES:
        return {
            "memory_type": normalized_type,
            "content": clean_content,
            "source_message": source_message,
            "should_save": False,
            "owner_confirmation_required": False,
            "owner_confirmed": bool(owner_confirmed),
            "retention": retention or "session",
            "sensitivity_level": normalized_sensitivity,
            "reason": "Temporary runtime context should stay short-term only.",
            "expires_at": expires_at,
            "blocked_reason": "temporary_context_not_permanent",
            "metadata": clean_metadata,
        }

    if normalized_type in ALLOWED_PERMANENT_MEMORY_TYPES:
        confirmation_required = normalized_type in OWNER_CONFIRMATION_REQUIRED_TYPES
        confirmed = bool(owner_confirmed)
        return {
            "memory_type": normalized_type,
            "content": clean_content,
            "source_message": source_message,
            "should_save": confirmed and not confirmation_required or confirmed,
            "owner_confirmation_required": confirmation_required,
            "owner_confirmed": confirmed,
            "retention": retention or "permanent",
            "sensitivity_level": normalized_sensitivity,
            "reason": (
                "Owner-confirmed permanent memory candidate."
                if confirmed
                else "Permanent memory candidate requires explicit owner confirmation."
            ),
            "expires_at": expires_at,
            "blocked_reason": None if confirmed else "owner_confirmation_required",
            "metadata": clean_metadata,
        }

    if normalized_type in ALLOWED_CUSTOMER_SALIENT_TYPES:
        return {
            "memory_type": normalized_type,
            "content": clean_content,
            "source_message": source_message,
            "should_save": True,
            "owner_confirmation_required": False,
            "owner_confirmed": True,
            "retention": retention or "permanent",
            "sensitivity_level": "normal",
            "reason": "Customer salient fact (1B allowlist) — auto-save.",
            "expires_at": expires_at,
            "blocked_reason": None,
            "metadata": clean_metadata,
        }

    return {
        "memory_type": normalized_type,
        "content": clean_content,
        "source_message": source_message,
        "should_save": False,
        "owner_confirmation_required": True,
        "owner_confirmed": bool(owner_confirmed),
        "retention": retention or "blocked",
        "sensitivity_level": normalized_sensitivity,
        "reason": "Memory type is not allowlisted for permanent save.",
        "expires_at": expires_at,
        "blocked_reason": "memory_type_not_allowed",
        "metadata": clean_metadata,
    }


def make_memory_write_decision_from_candidate(
    candidate: MemoryCandidateClassification | dict[str, Any],
) -> MemoryWriteDecisionPacket:
    """
    Converts a dry-run classification into the shared MemoryWriteDecisionPacket.
    This function performs no writes and no embedding calls.
    """
    return make_memory_write_decision_packet(
        should_save=bool(candidate.get("should_save", False)),
        memory_type=candidate.get("memory_type"),
        content=candidate.get("content"),
        reason=candidate.get("reason"),
        owner_confirmation_required=bool(candidate.get("owner_confirmation_required", False)),
        owner_confirmed=bool(candidate.get("owner_confirmed", False)),
        retention=candidate.get("retention", "blocked"),
        sensitivity_level=candidate.get("sensitivity_level", "normal"),
        source_message=candidate.get("source_message"),
        expires_at=candidate.get("expires_at"),
        blocked_reason=candidate.get("blocked_reason"),
    )


__all__ = [
    "ALLOWED_PERMANENT_MEMORY_TYPES",
    "ALLOWED_CUSTOMER_SALIENT_TYPES",
    "TEMPORARY_MEMORY_TYPES",
    "OWNER_CONFIRMATION_REQUIRED_TYPES",
    "MEMORY_SAFETY_CATEGORIES",
    "BLOCKED_SENSITIVITY_LEVELS",
    "MemoryCandidateClassification",
    "classify_memory_candidate",
    "make_memory_write_decision_from_candidate",
]

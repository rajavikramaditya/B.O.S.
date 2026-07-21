"""Standard Error Response builder helper for Neena API endpoints."""
from __future__ import annotations

from typing import Any, Optional
from services.brain.contracts_foundation import ErrorResponse


def build_error_response(
    error_code: str,
    message: str,
    recoverable: bool = False,
    details: Optional[dict[str, Any]] = None,
    next_action: Optional[str] = None,
) -> dict[str, Any]:
    """Builds a standardized error response dictionary (AGENTS rule 6).

    Fields: error_code, message, details, recoverable, next_action (+ ok, timestamp).
    Use this for every API/action error instead of ad-hoc strings.
    """
    resp = ErrorResponse(
        ok=False,
        error_code=error_code,
        message=message,
        details=details,
        recoverable=recoverable,
        next_action=next_action,
    )
    return resp.dict()

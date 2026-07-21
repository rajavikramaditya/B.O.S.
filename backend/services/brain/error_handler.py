"""Global error envelope — upgrades every HTTPException to the AGENTS rule-6 shape.

Rule 6: no random error strings; errors carry
`error_code, message, details, recoverable, next_action` (+ `ok`, `timestamp`).

This is wired once in `main.py` as a global exception handler, so ALL endpoints
conform without editing each call site. It is **backward compatible**: the
original `detail` key is preserved, so existing frontend/mobile parsing
(`data.detail || data.message`) keeps working while the structured fields are
added on top.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.error_response import build_error_response

# HTTP status codes that are inherently safe to retry.
_RECOVERABLE_STATUS = {429, 503, 504}


class NeenaHTTPError(StarletteHTTPException):
    """HTTPException that carries the rule-6 structured fields.

    Use this (instead of a bare HTTPException) when an endpoint wants to give the
    caller an explicit error_code / next_action. Plain HTTPExceptions are still
    upgraded automatically by the handler below.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        error_code: Optional[str] = None,
        recoverable: Optional[bool] = None,
        next_action: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.error_code = error_code or f"HTTP_{status_code}"
        self.recoverable = (status_code in _RECOVERABLE_STATUS) if recoverable is None else recoverable
        self.next_action = next_action
        self.details = details


def build_http_error_body(exc: StarletteHTTPException) -> dict[str, Any]:
    """Build the rule-6 envelope for an HTTPException (backward compatible)."""
    status = exc.status_code
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    error_code = getattr(exc, "error_code", None) or f"HTTP_{status}"
    recoverable = getattr(exc, "recoverable", None)
    if recoverable is None:
        recoverable = status in _RECOVERABLE_STATUS
    next_action = getattr(exc, "next_action", None)
    details = getattr(exc, "details", None)

    body = build_error_response(
        error_code=error_code,
        message=message,
        recoverable=bool(recoverable),
        details=details,
        next_action=next_action,
    )
    # Backward compatibility: keep the original FastAPI `detail` shape.
    body["detail"] = detail
    return body


async def neena_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    del request  # unused; signature required by FastAPI
    return JSONResponse(
        status_code=exc.status_code,
        content=build_http_error_body(exc),
        headers=getattr(exc, "headers", None),
    )


__all__ = ["NeenaHTTPError", "neena_http_exception_handler", "build_http_error_body"]

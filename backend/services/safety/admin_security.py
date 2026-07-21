"""
M4-A7 — Command Center access guard (local-only default + optional admin token).

No secrets are logged. Tokens read from environment only.
"""
from __future__ import annotations

import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.safety.admin_unlock import (
    SESSION_COOKIE_NAME,
    unlock_phrase_configured,
    verify_session_token,
)

# Liveness probes — answered on the event loop before other middleware/routes.
HEALTH_PROBE_EXACT = (
    "/healthz",
    "/api/healthz",
)

# Public/mobile API and inbound webhooks bypass local-only guard.
PUBLIC_BYPASS_PREFIXES = (
    "/api/public/",
    "/api/leads/inbound-webhook",
    "/api/public/whatsapp-inbound",
    "/api/whatsapp/webhook",
    "/api/azuracast/webhook",
)

# Write/admin paths that require token when ADMIN_AUTH_ENABLED=true.
ADMIN_WRITE_PREFIXES = (
    "/api/neena/chat",
    "/api/neena/cockpit-action",
    "/api/neena/cockpit-jobs",
    "/api/neena/feature-flags",
    "/api/admin/",
    "/api/broadcast/capsules/",
    "/api/broadcast/capsules",
    "/api/config/key",
    "/api/runtime/command",
    "/api/market-rates/",
    "/api/neena/capsules/",
    "/api/neena/capsules",
)

# Paths exempt from admin auth (unlock handshake + lock).
ADMIN_AUTH_EXEMPT_EXACT = (
    "/api/admin/unlock",
    "/api/admin/lock",
)

# Authenticated GET paths (job polling) when admin auth enabled.
ADMIN_AUTH_GET_PREFIXES = (
    "/api/neena/cockpit-jobs/",
    "/api/neena/capsules/",
    "/api/neena/capsules",
    "/api/broadcast/capsules/",
    "/api/broadcast/capsules",
    "/api/neena/interaction-records/",
    "/api/neena/working-context",
    "/api/neena/feature-flags",
)


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def command_center_local_only() -> bool:
    explicit = os.environ.get("COMMAND_CENTER_LOCAL_ONLY", "").strip().lower()
    if explicit in ("0", "false", "no", "off"):
        return False
    if explicit in ("1", "true", "yes", "on"):
        return True
    runtime = (os.environ.get("RUNTIME_MODE") or "LOCAL_TEST_MODE").upper()
    return "LOCAL" in runtime or runtime in ("", "LOCAL_TEST_MODE")


def admin_auth_enabled() -> bool:
    return _env_truthy("ADMIN_AUTH_ENABLED", "false")


def _client_host(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else ""


def is_local_client(request: Request) -> bool:
    host = _client_host(request)
    if host in ("127.0.0.1", "::1", "localhost"):
        return True
    if host.startswith("127.") or host == "0:0:0:0:0:0:0:1":
        return True
    return False


def _path_bypasses_local_guard(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PUBLIC_BYPASS_PREFIXES)


def _is_admin_write_path(path: str, method: str) -> bool:
    if method.upper() in ("GET", "HEAD", "OPTIONS"):
        return False
    return any(path.startswith(prefix) for prefix in ADMIN_WRITE_PREFIXES)


def _is_admin_auth_get_path(path: str, method: str) -> bool:
    if method.upper() != "GET":
        return False
    return any(path.startswith(prefix) for prefix in ADMIN_AUTH_GET_PREFIXES)


def _verify_admin_api_key(request: Request) -> bool:
    expected = (os.environ.get("ADMIN_API_KEY") or "").strip()
    if not expected:
        return False
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() == expected
    header_key = request.headers.get("x-admin-key", "")
    return header_key.strip() == expected


def _verify_admin_session_cookie(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    return verify_session_token(token)


def _verify_admin_auth(request: Request) -> bool:
    if _verify_admin_api_key(request):
        return True
    return _verify_admin_session_cookie(request)


def _is_admin_auth_exempt(path: str) -> bool:
    return path in ADMIN_AUTH_EXEMPT_EXACT


def admin_session_active(request: Request) -> bool:
    return _verify_admin_session_cookie(request)


def admin_credentials_configured() -> bool:
    has_key = bool((os.environ.get("ADMIN_API_KEY") or "").strip())
    return has_key or unlock_phrase_configured()


def security_status(request: Request | None = None) -> dict:
    local_only = command_center_local_only()
    auth_on = admin_auth_enabled()
    has_key = bool((os.environ.get("ADMIN_API_KEY") or "").strip())
    has_phrase = unlock_phrase_configured()
    creds = admin_credentials_configured()
    auth_required = auth_on and creds
    exposure = "local_only" if local_only else "network_exposed"
    if not local_only and auth_required:
        exposure = "network_exposed_with_admin_auth"
    elif not local_only and not auth_required:
        exposure = "network_exposed_auth_missing"
    session_unlocked = admin_session_active(request) if request is not None else False
    return {
        "command_center_local_only": local_only,
        "admin_auth_enabled": auth_on,
        "admin_api_key_configured": has_key,
        "admin_unlock_phrase_configured": has_phrase,
        "auth_required": auth_required,
        "session_unlocked": session_unlocked,
        "local_only": local_only,
        "exposure_mode": exposure,
        "token_header_name": "Authorization",
        "token_header_format": "Bearer",
        "alternate_header": "X-Admin-Key",
        "unlock_mode": "phrase_cookie" if has_phrase else ("api_key" if has_key else None),
        "message": (
            "Sir, Command Center locked hai. Pehle owner unlock phrase boliye ya likhiye."
            if auth_required and has_phrase
            else (
                "Enter ADMIN_API_KEY in Command Center unlock to use voice and broadcast actions."
                if auth_required and has_key
                else None
            )
        ),
        "launch_blocker": (
            "Admin console must remain local-only until admin auth is configured."
            if exposure == "network_exposed_auth_missing"
            else None
        ),
    }


class HealthProbeMiddleware(BaseHTTPMiddleware):
    """Fast liveness path that does not wait on thread-pool heavy routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or "/"
        if path in HEALTH_PROBE_EXACT:
            return JSONResponse({"ok": True, "service": "neena-backend"})
        return await call_next(request)


class CommandCenterSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or "/"
        method = request.method.upper()

        if _path_bypasses_local_guard(path):
            return await call_next(request)

        if command_center_local_only() and not is_local_client(request):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Command Center is local-only. Use localhost or set COMMAND_CENTER_LOCAL_ONLY=false with ADMIN_AUTH_ENABLED.",
                    "security": security_status(),
                },
            )

        if _is_admin_auth_exempt(path):
            return await call_next(request)

        if admin_auth_enabled() and admin_credentials_configured() and _is_admin_write_path(path, method):
            if not _verify_admin_auth(request):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Command Center locked. Owner unlock phrase or admin credentials required.",
                    },
                )

        if admin_auth_enabled() and admin_credentials_configured() and _is_admin_auth_get_path(path, method):
            if not _verify_admin_auth(request):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Command Center locked. Owner unlock phrase or admin credentials required.",
                    },
                )

        return await call_next(request)


__all__ = [
    "HealthProbeMiddleware",
    "CommandCenterSecurityMiddleware",
    "admin_auth_enabled",
    "admin_credentials_configured",
    "admin_session_active",
    "command_center_local_only",
    "is_local_client",
    "security_status",
]

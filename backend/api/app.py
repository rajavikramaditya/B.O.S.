"""B.O.S. HTTP Application v1.0

FastAPI app factory: API routes, OpenAPI docs and the single-page dashboard.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bootstrap.platform import VERSION, Platform
from bootstrap.settings import PlatformSettings

from .routes import channels, integrations, mcp, public_v1, system, workspace

API_PREFIXES = ("/api", "/v1", "/mcp")

DESCRIPTION = """
**B.O.S. — Business Operating System.** An AI operator that runs a business proactively:
it guides customers, follows up, keeps records and asks the owner only when it matters.

* **Public API (`/v1`)** — authenticate with `Authorization: Bearer bos_live_...` (create keys in Integrations → Developer).
* **Webhooks** — subscribe to signed events (`BOS-Signature: t=..,v1=..`, HMAC-SHA256 of `"<t>.<body>"`).
* **MCP** — point any MCP client at `/mcp` with the same API key.
"""


def create_app(settings: Optional[PlatformSettings] = None, start_scheduler: bool = True) -> FastAPI:
    settings = settings or PlatformSettings.from_env()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Platform.start(settings, start_scheduler=start_scheduler)
        yield
        Platform.stop()

    app = FastAPI(
        title="B.O.S. API",
        version=VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/reference",
        openapi_url="/api/openapi.json",
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    for module in (system, workspace, integrations, public_v1, channels, mcp):
        app.include_router(module.router)

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("bos.api").exception("Unhandled error", exc_info=exc)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    _mount_dashboard(app, settings.frontend_dist)
    return app


def _mount_dashboard(app: FastAPI, dist: Path) -> None:
    """Serve the built dashboard with client-side routing fallback."""
    index = dist / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        def no_dashboard() -> JSONResponse:
            return JSONResponse({"name": "B.O.S.", "version": VERSION, "docs": "/api/docs", "dashboard": "not built (run npm run build in frontend/)"})

        return

    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(tuple(p.lstrip("/") for p in API_PREFIXES)):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

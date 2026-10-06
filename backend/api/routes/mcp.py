"""B.O.S. MCP Route v1.0

Streamable HTTP endpoint for the MCP server (JSON responses, no SSE stream).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from integrations.mcp_server import McpServer

from ..security import Principal, require_scope

router = APIRouter(tags=["MCP"])


@router.post("/mcp")
async def mcp_endpoint(request: Request, principal: Principal = Depends(require_scope("operator"))) -> Any:
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, status_code=400)
    server = McpServer(client_name=principal.name, client_id=principal.id, scopes=principal.scopes)
    if isinstance(body, list):
        replies = [r for r in [await run_in_threadpool(server.handle, m) for m in body] if r is not None]
        return JSONResponse(replies) if replies else Response(status_code=202)
    reply = await run_in_threadpool(server.handle, body)
    return JSONResponse(reply) if reply is not None else Response(status_code=202)


@router.get("/mcp")
def mcp_stream_not_supported() -> Response:
    # This server answers every request inline, so it offers no server-initiated stream.
    return Response(status_code=405, headers={"Allow": "POST"})

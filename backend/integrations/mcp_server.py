"""B.O.S. MCP Server v1.0

Model Context Protocol (JSON-RPC 2.0 over Streamable HTTP, JSON responses) so
Claude, Cursor and other MCP clients can operate the business through B.O.S.
Every tool call goes through the Runtime Gateway — agents get no shortcut
around Policy or Verification.
"""

import json
from typing import Any, Callable, Dict, Optional

from gateway.runtime_gateway import RuntimeGateway
from runtime.cognition import RuntimeCognition
from workspace.approvals import ApprovalRepository
from workspace.records import ContactRepository, TaskRepository

PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "ask_operator",
        "description": "Ask the B.O.S. business operator to handle something in plain language. "
        "It understands, plans, acts within policy and reports verified results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What you need done or want to know."},
                "conversation_id": {"type": "string", "description": "Reuse to continue the same thread."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "run_action",
        "description": "Run one capability action directly (see list_capabilities). External or sensitive actions wait for owner approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "capability": {"type": "string"},
                "action": {"type": "string"},
                "params": {"type": "object"},
                "reason": {"type": "string"},
            },
            "required": ["capability", "action"],
        },
    },
    {"name": "list_capabilities", "description": "List capabilities, actions, parameters and risk levels.", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "list_contacts",
        "description": "Search the business's contacts.",
        "inputSchema": {"type": "object", "properties": {"search": {"type": "string"}, "stage": {"type": "string"}}},
    },
    {
        "name": "list_tasks",
        "description": "List tasks (open by default).",
        "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "done", "all"]}}},
    },
    {"name": "list_pending_approvals", "description": "Actions waiting for the owner's decision.", "inputSchema": {"type": "object", "properties": {}}},
]


class McpServer:
    """Stateless JSON-RPC handler bound to the calling API key's identity."""

    def __init__(self, client_name: str, client_id: str):
        self.client_name = client_name
        self.client_id = client_id

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method", "")
        msg_id = message.get("id")
        if msg_id is None:  # notification (e.g. notifications/initialized)
            return None
        handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "initialize": self._initialize,
            "ping": lambda _p: {},
            "tools/list": lambda _p: {"tools": TOOLS},
            "tools/call": self._call_tool,
        }
        handler = handlers.get(method)
        if handler is None:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        try:
            return {"jsonrpc": "2.0", "id": msg_id, "result": handler(message.get("params") or {})}
        except Exception as ex:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(ex)}}

    @staticmethod
    def _initialize(params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "bos", "title": "B.O.S. Business Operating System", "version": "1.0.0"},
            "instructions": "Use ask_operator for anything in plain language; use run_action for precise operations.",
        }

    def _call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name == "ask_operator":
            result = RuntimeGateway.submit(
                role="employee",
                message=str(args.get("message") or ""),
                channel="mcp",
                conversation_id=str(args.get("conversation_id") or f"mcp:{self.client_id}"),
                sender_name=self.client_name,
                source=f"mcp:{self.client_name}",
            )
            payload: Any = {
                "reply": result.get("reply"),
                "conversation_id": result.get("conversation_id"),
                "executed": [{"title": s["title"], "success": s["success"], "error": s.get("error")} for s in result.get("executed_steps", [])],
                "awaiting_approval": [a["title"] for a in result.get("approvals", [])],
            }
        elif name == "run_action":
            step = {
                "capability": args.get("capability"),
                "action": args.get("action"),
                "params": args.get("params") or {},
                "title": f"{args.get('capability')}.{args.get('action')}",
                "reason": args.get("reason") or f"Requested by {self.client_name}",
            }
            result = RuntimeGateway.submit(
                role="employee",
                message=step["reason"],
                channel="mcp",
                conversation_id=f"mcp:{self.client_id}",
                sender_name=self.client_name,
                raw_payload={"plan": [step]},
                source=f"mcp:{self.client_name}",
            )
            payload = {
                "executed": result.get("executed_steps"),
                "awaiting_approval": [a["title"] for a in result.get("approvals", [])],
                "denied": result.get("denied_steps"),
            }
        elif name == "list_capabilities":
            payload = RuntimeCognition.capability_catalog()
        elif name == "list_contacts":
            payload = ContactRepository.list(str(args.get("search") or ""), str(args.get("stage") or ""), limit=50)
        elif name == "list_tasks":
            status = str(args.get("status") or "open")
            payload = TaskRepository.list("" if status == "all" else status, limit=50)
        elif name == "list_pending_approvals":
            payload = ApprovalRepository.list("pending", limit=50)
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}], "isError": False}

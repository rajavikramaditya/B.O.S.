"""B.O.S. Connector Catalog v1.0

Declarative manifests for every integration the dashboard can connect.
Adding a connector = adding a manifest here plus its adapter/provider.
"""

from typing import Any, Dict, List, Optional

CONNECTORS: List[Dict[str, Any]] = [
    {
        "id": "anthropic",
        "name": "Claude",
        "vendor": "Anthropic",
        "category": "AI model",
        "description": "Claude powers understanding, planning and replies. Recommended.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True, "placeholder": "sk-ant-..."}],
        "docs_url": "https://console.anthropic.com/settings/keys",
        "kind": "ai",
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "vendor": "Google",
        "category": "AI model",
        "description": "Use Google Gemini as the AI model or as a backup.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True, "placeholder": "AIza..."}],
        "docs_url": "https://aistudio.google.com/app/apikey",
        "kind": "ai",
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "vendor": "Telegram",
        "category": "Messaging channel",
        "description": "Customers chat with your business bot; B.O.S. answers, guides and follows up.",
        "fields": [{"key": "bot_token", "label": "Bot token (from @BotFather)", "secret": True, "placeholder": "123456:ABC..."}],
        "docs_url": "https://core.telegram.org/bots#how-do-i-create-a-bot",
        "kind": "channel",
        "inbound": "/v1/channels/telegram/webhook",
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp Business",
        "vendor": "Meta",
        "category": "Messaging channel",
        "description": "Answer and guide customers on WhatsApp through the official Cloud API.",
        "fields": [
            {"key": "access_token", "label": "Permanent access token", "secret": True},
            {"key": "phone_number_id", "label": "Phone number ID", "secret": False},
            {"key": "verify_token", "label": "Webhook verify token (choose any phrase)", "secret": True},
            {"key": "app_secret", "label": "App secret (signs incoming webhooks)", "secret": True},
        ],
        "docs_url": "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started",
        "kind": "channel",
        "inbound": "/v1/channels/whatsapp/webhook",
    },
    {
        "id": "email",
        "name": "Email (SMTP)",
        "vendor": "Any provider",
        "category": "Messaging channel",
        "description": "Send follow-ups and updates from your own mailbox (Gmail, Outlook, Zoho, SES...).",
        "fields": [
            {"key": "host", "label": "SMTP host", "secret": False, "placeholder": "smtp.gmail.com"},
            {"key": "port", "label": "Port", "secret": False, "placeholder": "587"},
            {"key": "username", "label": "Username", "secret": False},
            {"key": "password", "label": "Password / app password", "secret": True},
            {"key": "from_address", "label": "From address", "secret": False},
        ],
        "docs_url": "https://support.google.com/mail/answer/185833",
        "kind": "channel",
    },
    {
        "id": "webhooks",
        "name": "Webhooks",
        "vendor": "B.O.S.",
        "category": "Automation",
        "description": "Send signed events to Zapier, Make, n8n or your own systems in real time.",
        "fields": [],
        "kind": "builtin",
    },
    {
        "id": "rest_api",
        "name": "REST API",
        "vendor": "B.O.S.",
        "category": "Developer",
        "description": "Versioned REST API with OpenAPI docs and scoped API keys.",
        "fields": [],
        "kind": "builtin",
        "docs_path": "/api/docs",
    },
    {
        "id": "mcp",
        "name": "MCP Server",
        "vendor": "B.O.S.",
        "category": "AI agents",
        "description": "Let Claude, Cursor and other MCP clients operate your business through B.O.S.",
        "fields": [],
        "kind": "builtin",
        "inbound": "/mcp",
    },
]


def inbound_channel_ids() -> List[str]:
    """Channels customers can message the business through (outbound-only ones such as SMTP excluded)."""
    return [c["id"] for c in CONNECTORS if c.get("kind") == "channel" and c.get("inbound")]


def get_connector(connector_id: str) -> Optional[Dict[str, Any]]:
    return next((c for c in CONNECTORS if c["id"] == connector_id), None)

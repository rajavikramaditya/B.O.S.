"""B.O.S. Adapter Router v0.1

Routes capability requests to active external adapters based on action and channel.
"""

from typing import Any, Dict, List, Optional
from .adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus
from .registry import AdapterRegistry
from .messaging import WhatsAppAdapter, TelegramAdapter, EmailAdapter
from .system import CalendarAdapter, VoiceAdapter, PaymentsAdapter, StorageAdapter


class AdapterRouter:
    """Central routing mechanism directing platform actions to external adapters."""

    @classmethod
    def initialize_defaults(cls) -> None:
        """Register default platform adapters if not already present."""
        defaults = [
            WhatsAppAdapter(),
            TelegramAdapter(),
            EmailAdapter(),
            CalendarAdapter(),
            VoiceAdapter(),
            PaymentsAdapter(),
            StorageAdapter(),
        ]
        for ad in defaults:
            if not AdapterRegistry.get(ad.name):
                ad.connect()
                AdapterRegistry.register(ad)

    @classmethod
    def route_action(
        cls,
        action: str,
        channel: str = "default",
        recipient: str = "",
        payload: Dict[str, Any] | None = None,
    ) -> AdapterResponse:
        cls.initialize_defaults()

        # Map channel or action to adapter
        chan_lower = (channel or "").lower()
        action_lower = (action or "").lower()

        adapter: Optional[Any] = None

        if chan_lower in ("whatsapp", "wa"):
            adapter = AdapterRegistry.get("whatsapp")
        elif chan_lower in ("telegram", "tg"):
            adapter = AdapterRegistry.get("telegram")
        elif chan_lower in ("email", "mail"):
            adapter = AdapterRegistry.get("email")
        elif chan_lower in ("calendar", "schedule"):
            adapter = AdapterRegistry.get("calendar")
        elif chan_lower in ("voice", "sip", "call"):
            adapter = AdapterRegistry.get("voice")
        elif chan_lower in ("payments", "pay", "stripe"):
            adapter = AdapterRegistry.get("payments")
        elif chan_lower in ("storage", "s3", "file"):
            adapter = AdapterRegistry.get("storage")

        # Action fallback mapping
        if not adapter:
            if "schedule" in action_lower or "meeting" in action_lower:
                adapter = AdapterRegistry.get("calendar")
            elif "call" in action_lower or "audio" in action_lower:
                adapter = AdapterRegistry.get("voice")
            elif "pay" in action_lower or "charge" in action_lower:
                adapter = AdapterRegistry.get("payments")
            elif "doc" in action_lower or "file" in action_lower:
                adapter = AdapterRegistry.get("storage")
            else:
                adapter = AdapterRegistry.get("whatsapp")

        if not adapter:
            return AdapterResponse(
                success=False,
                status=AdapterStatus.FAILED,
                error_message=f"No suitable adapter found for action '{action}' on channel '{channel}'",
            )

        request = AdapterRequest(
            action=action,
            recipient=recipient,
            payload=payload or {},
            channel=channel,
        )
        return adapter.execute_request(request)


# Auto-initialize
AdapterRouter.initialize_defaults()

"""B.O.S. Messaging Adapters Package v0.1

Provides WhatsAppAdapter, TelegramAdapter, and EmailAdapter.
"""

from .whatsapp_adapter import WhatsAppAdapter
from .telegram_adapter import TelegramAdapter
from .email_adapter import EmailAdapter

__all__ = [
    "WhatsAppAdapter",
    "TelegramAdapter",
    "EmailAdapter",
]

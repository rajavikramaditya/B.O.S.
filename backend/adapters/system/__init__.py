"""B.O.S. System Adapters Package v0.1

Provides CalendarAdapter, VoiceAdapter, PaymentsAdapter, and StorageAdapter.
"""

from .calendar_adapter import CalendarAdapter
from .voice_adapter import VoiceAdapter
from .payments_adapter import PaymentsAdapter
from .storage_adapter import StorageAdapter

__all__ = [
    "CalendarAdapter",
    "VoiceAdapter",
    "PaymentsAdapter",
    "StorageAdapter",
]

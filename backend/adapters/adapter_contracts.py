"""B.O.S. Adapter Contracts v0.1

Data contracts for request and response structures used across external system adapters.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AdapterStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


@dataclass
class AdapterRequest:
    """Standardized request payload passed to an adapter."""
    action: str
    recipient: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    channel: str = "default"
    request_id: str = field(default_factory=lambda: f"adpreq_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "recipient": self.recipient,
            "payload": self.payload,
            "channel": self.channel,
            "timestamp": self.timestamp,
        }


@dataclass
class AdapterResponse:
    """Standardized response returned by an adapter."""
    success: bool
    status: AdapterStatus | str
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    response_id: str = field(default_factory=lambda: f"adpres_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "success": self.success,
            "status": str(self.status.value if hasattr(self.status, "value") else self.status),
            "data": self.data,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }

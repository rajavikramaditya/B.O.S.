"""B.O.S. Observation Engine v0.1

Stage 1 of Runtime Lifecycle: Normalizes incoming inputs into a unified NormalizedRequest object.
"""

import time
import uuid
from typing import Any, Dict
from .contracts import NormalizedRequest, ActorRole


class ObservationEngine:
    """Receives and normalizes all incoming requests into the system."""

    @staticmethod
    def observe(
        *,
        role: ActorRole | str = "customer",
        message: str = "",
        selected_model: str = "auto",
        sender_name: str = "ji",
        phone: str = "",
        channel: str = "command_center",
        raw_payload: Dict[str, Any] | None = None,
    ) -> NormalizedRequest:
        role_clean: ActorRole = "customer"
        role_str = (role or "customer").strip().lower()
        if role_str in ("owner", "customer", "employee"):
            role_clean = role_str  # type: ignore

        req_id = f"req_{uuid.uuid4().hex[:12]}"
        return NormalizedRequest(
            request_id=req_id,
            role=role_clean,
            message=message or "",
            channel=channel or "command_center",
            selected_model=selected_model or "auto",
            sender_name=sender_name or "ji",
            phone=phone or "",
            timestamp=time.time(),
            raw_payload=raw_payload or {},
        )

"""B.O.S. Observation Engine v1.0

Stage 1 of Runtime Lifecycle: Normalizes incoming inputs into a unified NormalizedRequest object.
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from .contracts import NormalizedRequest, ActorRole

KNOWN_ROLES = ("owner", "customer", "employee", "system")


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
        conversation_id: str = "",
        actor_ref: str = "",
        grants: Optional[List[str]] = None,
    ) -> NormalizedRequest:
        role_str = (role or "customer").strip().lower()
        role_clean: ActorRole = role_str if role_str in KNOWN_ROLES else "customer"  # type: ignore[assignment]

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
            conversation_id=conversation_id or f"{channel or 'runtime'}:{req_id}",
            actor_ref=actor_ref or "",
            grants=list(grants) if grants is not None else None,
        )

"""B.O.S. Approval Policy v0.1

Evaluates human-in-the-loop owner approval requirements.
"""

from typing import Any, Dict


class ApprovalPolicy:
    """Evaluates whether an action requires explicit human confirmation."""

    PROTECTED_ACTIONS = frozenset({
        "send_azuracast",
        "approve_latest_script",
        "approve_capsule",
        "fix_app_listener_path",
        "assign_capsule_to_playlist",
        "ensure_playback",
        "generate_audio",
        "prepare_capsule_audio",
    })

    @classmethod
    def evaluate(cls, action: str, params: Dict[str, Any], role: str = "customer") -> str:
        if role != "owner":
            return "ALLOW"

        if action in cls.PROTECTED_ACTIONS or params.get("requires_approval"):
            return "CONFIRM"

        return "ALLOW"

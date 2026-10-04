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

    @classmethod
    def requires_human(cls, risk: str, autopilot_mode: str) -> bool:
        """Metadata-driven approval rule shared by every capability.

        risk:  read | safe | external | sensitive  (declared by the capability)
        mode:  off | assist | autopilot | autonomous  (chosen by the owner)
        """
        if risk == "read":
            return False
        if risk == "sensitive":
            return True
        if autopilot_mode == "autonomous":
            return False
        if autopilot_mode in ("assist", "off"):
            return True
        return risk != "safe"

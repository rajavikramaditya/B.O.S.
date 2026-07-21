"""B.O.S. Decision Rules v0.1

Rule evaluation logic for risk assessment, business approval, retries, and fallbacks.
"""

from typing import Any, Dict, List, Tuple


class DecisionRules:
    """Evaluates risk scores and business execution constraints."""

    # High-risk actions requiring explicit confirmation
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
    def evaluate_risk(cls, action: str, params: Dict[str, Any], role: str) -> Tuple[float, str, bool]:
        """Return (risk_score, risk_level, approval_required)."""
        if role != "owner":
            return 0.1, "LOW", False

        if action in cls.PROTECTED_ACTIONS:
            return 0.8, "HIGH", True

        if any(w in action for w in ("delete", "remove", "wipe", "restart")):
            return 0.95, "CRITICAL", True

        return 0.2, "LOW", False

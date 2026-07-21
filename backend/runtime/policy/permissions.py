"""B.O.S. Permissions Policy v0.1

Evaluates actor role permissions and access control.
"""

from typing import Any, Dict, List


class PermissionsPolicy:
    """Evaluates actor roles and action permissions."""

    ROLE_PERMISSIONS = {
        "owner": ["*"],
        "customer": ["chat", "inquiry", "send_message"],
        "employee": ["inquiry", "task_update"],
    }

    @classmethod
    def evaluate(cls, action: str, role: str, permissions: List[str] | None = None) -> str:
        role_clean = (role or "customer").lower()
        allowed_actions = cls.ROLE_PERMISSIONS.get(role_clean, [])

        if "*" in allowed_actions or action in allowed_actions:
            return "ALLOW"

        if permissions and ("*" in permissions or action in permissions):
            return "ALLOW"

        if role_clean == "customer" and action not in allowed_actions:
            return "DENY"

        return "ESCALATE"

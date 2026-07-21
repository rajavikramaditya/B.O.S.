"""B.O.S. Security Policy v0.1

Evaluates security risks, forbidden commands, and system safety.
"""

from typing import Any, Dict


class SecurityPolicy:
    """Enforces safety kernel, forbidden commands, and injection checks."""

    FORBIDDEN_KEYWORDS = (
        "rm -rf", "drop database", "truncate", "shutdown", "format drive",
        "systemctl stop", "killall",
    )

    @classmethod
    def evaluate(cls, action: str, params: Dict[str, Any], raw_text: str = "") -> str:
        text_lower = (raw_text or "").lower()
        if any(keyword in text_lower for keyword in cls.FORBIDDEN_KEYWORDS):
            return "DENY"

        if any(keyword in action.lower() for keyword in ("drop", "truncate", "system_shutdown")):
            return "DENY"

        return "ALLOW"

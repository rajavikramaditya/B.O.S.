"""Confirm / forbidden helpers + diagnostics exact-match only.

AGENTS hygiene: no Hindi/Hinglish phrase NLU for understanding.
Owner intent classification is interpreter → catalog tools.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_DIRECT_DIAGNOSTICS = frozenset(
    {
        "diagnostics kro",
        "diagnostics run karo",
        "run diagnostics",
        "diagnostics",
    }
)


def is_exact_command(message: str, llm_live: bool = False) -> bool:
    """True only for exact diagnostics strings (AGENTS allowed exact UI/tool commands).

    llm_live is ignored — casual chat never bypasses the interpreter via this helper.
    """
    del llm_live
    return (message or "").lower().strip() in _DIRECT_DIAGNOSTICS


def route_intent(user_message: str, llm_live: bool = False) -> dict:
    """Legacy helper: diagnostics exact → DIAGNOSTICS; else CHAT_CONVERSATION."""
    del llm_live
    if is_exact_command(user_message):
        return {
            "intent_type": "DIAGNOSTICS",
            "target_module": "neena_brain",
            "confidence": 1.0,
        }
    return {
        "intent_type": "CHAT_CONVERSATION",
        "target_module": "neena_brain",
        "confidence": 0.50,
    }


CONFIRMATION_ONLY_PHRASES = {
    "confirm",
    "yes",
    "haa",
    "ha",
    "haan",
    "hann",
    "han",
    "ok",
    "okay",
    "approve",
    "permission granted",
}

FORBIDDEN_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+",
    r"\bformat\s+",
    r"\bshutdown\b",
    r"\bpowershell\b",
    r"\bcmd\s*/c\b",
    r"\bbash\b",
    r"\bexec\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bssh\b",
    r"\bscp\b",
    r"\bgit\s+reset\b",
    r"\bedit\s+\.env\b",
    r"\bmodify\s+\.env\b",
]


def is_confirmation_only(msg_lower: str) -> bool:
    cleaned = (msg_lower or "").lower().strip().strip(".!,?").strip()
    return cleaned in CONFIRMATION_ONLY_PHRASES


_AFFIRM_TOKENS = {
    "haan",
    "hann",
    "haa",
    "ha",
    "han",
    "yes",
    "ok",
    "okay",
    "confirm",
    "confirmed",
    "theek",
    "thik",
    "bilkul",
    "sahi",
    "zaroor",
    "approve",
    "approved",
    "yep",
    "yup",
}
_NEGATE_TOKENS = {
    "nahi",
    "nahin",
    "mat",
    "no",
    "cancel",
    "ruk",
    "ruko",
    "band",
    "rehne",
    "chhodo",
    "chhod",
    "na",
    "nope",
}


def is_affirmative_reply(msg_lower: str) -> bool:
    """Context-gated yes-detector for a pending yes/no confirmation gate.

    Only meaningful when a pending action/candidate is already active. Recognizes
    natural affirmatives ('haan bilkul save kar do', 'theek hai kar do') while a
    negation word anywhere makes it False. Not used for open intent classification.
    """
    words = set(re.findall(r"[a-z]+", msg_lower or ""))
    if words & _NEGATE_TOKENS:
        return False
    if words & _AFFIRM_TOKENS:
        return True
    return ("kar do" in msg_lower or "kardo" in msg_lower) and len(
        (msg_lower or "").split()
    ) <= 5


def contains_forbidden_command(msg_lower: str) -> bool:
    return any(re.search(pattern, msg_lower) for pattern in FORBIDDEN_COMMAND_PATTERNS)


# --- Deprecated phrase detectors (always False). Kept so old imports do not crash. ---


def is_whatsapp_restart_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_whatsapp_status_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_whatsapp_message_request(msg_lower: str) -> bool:
    """Deprecated phrase NLU — WhatsApp send goes via interpreter catalog tool."""
    del msg_lower
    return False


def is_diagnostics_request(msg_lower: str, routed: dict) -> bool:
    del routed
    return (msg_lower or "").strip() in _DIRECT_DIAGNOSTICS


def is_24hr_plan_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_source_tools_status_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_stream_status_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_live_stream_issue(msg_lower: str, routed: dict) -> bool:
    del msg_lower, routed
    return False


def is_center_status_request(msg_lower: str, routed: dict) -> bool:
    del msg_lower, routed
    return False


def is_schedule_read_request(msg_lower: str) -> bool:
    del msg_lower
    return False


def is_approval_voice_preview_command(msg_lower: str) -> bool:
    del msg_lower
    return False

"""Structural truth gate — no fake progress / timer / pause / outbound without tool facts.

Neena is a separate agent product that *manages* systems via tools; she must not
claim hands she does not have this turn.

Owner-facing customer *facts* are owned only by ``customer_whatsapp_recall`` —
this gate never lectures about customers; it hands off or stays quiet.
"""
from __future__ import annotations

import re
from typing import Any

# Deferred WhatsApp *status* asks (W3 worker can arm these).
_DEFERRED_STATUS_ASK = re.compile(
    r"\b((\d+)\s*min|paanch\s*min).{0,60}(bhej|whatsapp|status)|"
    r"\b(baad\s*(bhej|whatsapp)|timer\s*set).{0,40}(status|whatsapp|bhej|update)?\b",
    re.I,
)
# Wake/remind — no tool yet (still cannot).
_WAKE_REMIND_ASK = re.compile(
    r"\b(yaad\s*dila|jaga\s*dena|wake\s*me|remind\s*me|kal\s*subah\s*jaga)\b",
    re.I,
)
_PAUSE_DIAG_ASK = re.compile(
    r"\b(pause|band\s*kar|stop).{0,40}(diagnostic|deep\s*diag|stream_cache)|"
    r"(diagnostic|deep\s*diag).{0,40}(band|stop|pause)\b",
    re.I,
)
_FAKE_PROGRESS_IN_REPLY = re.compile(
    r"\b(timer\s*set|set\s*kar\s*diya|main\s*(abhi\s*)?(set|pause|band)\s*kar|"
    r"pause\s*kar\s*(diya|rahi)|jaga\s*dungi|remind(er)?\s*(set|laga)|"
    r"5\s*minute\s*(baad|me)\s*(bhej|update))\b",
    re.I,
)
# Fake third-party / invented WhatsApp send (LIVE turns 646/649).
_FAKE_OUTBOUND_IN_REPLY = re.compile(
    r"("
    r"send_whatsapp_message|"
    r"\b(main\s+)?(abhi\s+)?(unhe|usse|usko|unki|customer|listener|\w+\s+ji)\s+"
    r"(ko\s+)?(message|msg)\s+(bhej|bhejti|bhejungi|bhej\s+rahi|bhej\s+deti)|"
    r"\b(message|msg)\s+(bhej\s*(rahi|ti|ungi|kar)|bhej\s+kar\s+aapko\s+confirm)|"
    r"\b(turant|abhi)\s+\w*.{0,40}(message|msg)\s+bhej|"
    r"\btool\s+use\s+karke\s+(ye\s+)?message\s+bhej"
    r")",
    re.I,
)
# Invented "no customer messages" without a checked recall packet (LIVE 626/547).
_EMPTY_CUSTOMER_CLAIM = re.compile(
    r"("
    r"koi\s+(naya\s+)?(customer\s+)?(message|msg|inquiry)\s+nahi|"
    r"customer\s+message\s+nahi\s+aaya|"
    r"kisi\s+(ne\s+)?(message|msg)\s+nahi|"
    r"no\s+customer\s+(message|inquiry)|"
    r"found\s+none|"
    r"none\s+in\s+the\s+recent|"
    r"whatsapp\s+par\s+koi\s+customer"
    r")",
    re.I,
)
# Owner actually asked for customer facts (structural; not general NLU).
_CUSTOMER_FACT_ASK = re.compile(
    r"("
    r"\bcustomer\b|\blistener\b|\blead\b|\binquiry\b|"
    r"kis(i|e)?\s+(se\s+)?baat|"
    r"(message|msg).{0,24}(aaya|aaye|hui|hua)|"
    r"whatsapp.{0,40}(customer|baat|message|msg)"
    r")",
    re.I,
)
# Station/capsule/audio/queue *progress* (not design chat about tools).
_WORK_CLAIM_IN_REPLY = re.compile(
    r"("
    r"\b(audio|capsule|tts)\s+(generate|bana|bana\s*rahi|ban\s*rahi)|"
    r"\bgenerate\s+(kar\s*(rahi|deti|dungi|diya)|ho\s*rahi)|"
    r"\b(queue|trigger)\s*(me\s*)?(daal|laga|start|shuru)|"
    r"\b(command\s+bhej\s*(diya|di|rahi)|process\s+start)|"
    r"\btaiyaar\s*kar\s*(rahi|diya)|"
    r"\b(main\s+)?(abhi\s+)?(audio|capsule).{0,40}(bana\s*rahi|generate\s*kar)"
    r")",
    re.I,
)
# Soft "I'll do it now" theatre — not planning chat ("ho jayega" alone).
_COMMITMENT_WITHOUT_TOOL = re.compile(
    r"("
    r"\b(main\s+)?abhi\s+(kar\s*dungi|kar\s*deti|kar\s*rahi\s*hoon)\b|"
    r"\b(main\s+)?(yeh?\s+)?(kaam\s+)?(kar\s*dungi|kar\s*deti)\b|"
    r"\bshuru\s*kar\s*rahi\b"
    r")",
    re.I,
)
_OK_WORK_STATUSES = frozenset(
    {
        "ok",
        "needs_confirmation",
        "armed",
        "empty",
        "cannot",
        "running",
        "queued",
        "accepted",
    }
)

_CHAT_ACTIONS = frozenset(
    {
        "",
        "unknown",
        "conversation",
        "chat",
        "clarify",
        "clarification",
    }
)

_CUSTOMER_RECALL_TOOLS = frozenset({"customer_whatsapp_recall"})
_OUTBOUND_OK_TOOLS = frozenset(
    {
        "arm_deferred_status",
        "whatsapp_outbound",
        "send_owner_whatsapp_status",
        "notify_owner",
    }
)

# Brain hands these to the owning module instead of speaking as truth_gate.
NEEDS_CUSTOMER_RECALL = "needs_customer_recall"


def is_work_action(action: str | None) -> bool:
    a = (action or "").strip().lower()
    return bool(a) and a not in _CHAT_ACTIONS


def is_deferred_status_ask(message: str) -> bool:
    return bool(_DEFERRED_STATUS_ASK.search(message or ""))


def is_customer_fact_ask(message: str) -> bool:
    return bool(_CUSTOMER_FACT_ASK.search(message or ""))


def unavailable_action_reason(message: str) -> str | None:
    """If owner asked for a capability we must not fake, return reason code."""
    msg = message or ""
    if _PAUSE_DIAG_ASK.search(msg):
        return "no_pause_diagnostics_tool"
    if _WAKE_REMIND_ASK.search(msg) and not is_deferred_status_ask(msg):
        return "no_wake_reminder_tool"
    if is_deferred_status_ask(msg):
        try:
            from services.cockpit.deferred_status import is_deferred_worker_ready

            if is_deferred_worker_ready():
                return None
        except Exception:
            pass
        return "deferred_followthrough_not_armed"
    return None


def build_cannot_reply(reason: str) -> str:
    """Short effective honesty — no meta 'jhoot/nahi bolungi' theatre."""
    if reason == "no_pause_diagnostics_tool":
        return "Sir, diagnostics pause ka tool abhi nahi hai."
    if reason == "no_wake_reminder_tool":
        return "Sir, wake/remind worker abhi nahi hai."
    if reason == "deferred_followthrough_not_armed":
        return "Sir, deferred timer worker abhi armed nahi hai."
    if reason == "no_customer_outbound_tool":
        return "Sir, customer ko WhatsApp bhejne ka tool abhi nahi hai."
    if reason == "customer_recall_not_checked":
        # Prefer needs_customer_recall hand-off; keep short fallback.
        return "Sir, pehle customer WhatsApp check karna hoga."
    if reason == "tool_missing":
        return "Sir, iska tool abhi available nahi hai."
    if reason in ("no_tool_result", "work_claim_without_facts"):
        return "Sir, iska confirm tool result abhi nahi hai."
    if reason == NEEDS_CUSTOMER_RECALL:
        return "Sir, customer WhatsApp check karti hoon."
    return f"Sir, yeh abhi nahi ho sakta ({reason})."


def build_cannot_packet(reason: str, *, detail: str = "") -> dict[str, Any]:
    return {
        "tool": "truth_gate",
        "status": "cannot",
        "reason": reason,
        "detail": (detail or "")[:300],
        "neena_role": "separate_agent_product",
    }


def _packet_tool(factual_packet: dict[str, Any] | None) -> str:
    if not isinstance(factual_packet, dict):
        return ""
    return str(factual_packet.get("tool") or "").strip()


def _facts_allow_work_claims(factual_packet: dict[str, Any] | None) -> bool:
    """True when this turn has a real tool/job packet that can back progress talk."""
    if not isinstance(factual_packet, dict) or not factual_packet:
        return False
    if factual_packet.get("job_id"):
        return True
    tool = _packet_tool(factual_packet)
    if not tool:
        return False
    status = str(factual_packet.get("status") or "").strip().lower()
    if status in _OK_WORK_STATUSES:
        return True
    return bool(tool)


def enforce_truth_on_reply(
    message: str,
    reply: str,
    *,
    factual_packet: dict[str, Any] | None = None,
    action: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Replace invented progress claims when no factual tool packet this turn."""
    del action  # reserved for future action-aware scrubs
    text = (reply or "").strip()
    has_facts = _facts_allow_work_claims(factual_packet)
    tool = _packet_tool(factual_packet)
    if has_facts and tool == "arm_deferred_status":
        return text, None
    reason = unavailable_action_reason(message)
    if reason and not has_facts:
        pkt = build_cannot_packet(reason)
        return build_cannot_reply(reason), pkt
    if not has_facts and _FAKE_PROGRESS_IN_REPLY.search(text):
        pkt = build_cannot_packet("no_tool_result", detail="scrubbed_fake_progress")
        return build_cannot_reply("no_tool_result"), pkt
    # Fake third-party WhatsApp send / invented tool name.
    if _FAKE_OUTBOUND_IN_REPLY.search(text) and tool not in _OUTBOUND_OK_TOOLS:
        pkt = build_cannot_packet(
            "no_customer_outbound_tool", detail="scrubbed_fake_outbound"
        )
        return build_cannot_reply("no_customer_outbound_tool"), pkt
    # Customer empty-claim: only when owner asked — hand off to recall module.
    # Never lecture from truth_gate on Hello / unrelated chat (LIVE 822).
    if _EMPTY_CUSTOMER_CLAIM.search(text) and tool not in _CUSTOMER_RECALL_TOOLS:
        if is_customer_fact_ask(message):
            pkt = build_cannot_packet(
                NEEDS_CUSTOMER_RECALL, detail="hand_off_customer_whatsapp_recall"
            )
            return build_cannot_reply(NEEDS_CUSTOMER_RECALL), pkt
        return text, None
    # Capsule/audio/queue progress without tool/job facts this turn.
    if not has_facts and _WORK_CLAIM_IN_REPLY.search(text):
        pkt = build_cannot_packet(
            "work_claim_without_facts", detail="scrubbed_work_claim"
        )
        return build_cannot_reply("work_claim_without_facts"), pkt
    if not has_facts and _COMMITMENT_WITHOUT_TOOL.search(text):
        pkt = build_cannot_packet("no_tool_result", detail="scrubbed_commitment")
        return build_cannot_reply("no_tool_result"), pkt
    return text, None


__all__ = [
    "NEEDS_CUSTOMER_RECALL",
    "build_cannot_packet",
    "build_cannot_reply",
    "enforce_truth_on_reply",
    "is_customer_fact_ask",
    "is_deferred_status_ask",
    "is_work_action",
    "unavailable_action_reason",
]

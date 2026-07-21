"""Shared builder for live-ops factual result packets.

Deterministic layer returns short factual fallback + structured packet.
Final owner Hinglish is composed by maybe_humanize_report when allowed.
"""
from __future__ import annotations

from typing import Any


def build_live_ops_result(
    action_type: str,
    *,
    packet: dict[str, Any],
    fallback_line: str,
    **extras: Any,
) -> dict[str, Any]:
    """Standard live-ops chat payload: facts for LLM, readable fallback if LLM down."""
    out: dict[str, Any] = {
        "reply": (fallback_line or "").strip() or "No details.",
        "action_type": action_type,
        "factual_packet": packet,
        "gemini_calls": int(extras.pop("gemini_calls", 0) or 0),
    }
    out.update(extras)
    return out


__all__ = ["build_live_ops_result"]

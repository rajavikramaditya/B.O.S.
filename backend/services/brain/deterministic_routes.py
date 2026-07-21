"""Pre-interpreter deterministic gates — intentionally empty (AGENTS hygiene).

Owner understanding is interpreter → catalog JSON only.
Safety Kernel / exact confirm / slot extractors live elsewhere.
This module remains so call sites keep a stable import; it always returns None.
"""
from __future__ import annotations


def resolve_deterministic_action(message: str) -> dict | None:
    """No phrase/regex owner routing. Always defer to the interpreter."""
    del message
    return None


__all__ = ["resolve_deterministic_action"]

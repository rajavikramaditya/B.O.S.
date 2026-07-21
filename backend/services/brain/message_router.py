"""Compatibility — single brain entry lives on ``services.brain.brain``.

All callers should prefer ``from services.brain.brain import process_message``.
This module re-exports so old imports keep working.
"""
from __future__ import annotations

from services.brain.brain import ActorRole, process_message

__all__ = ["ActorRole", "process_message"]

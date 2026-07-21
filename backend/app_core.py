"""Shared app-core singletons (rule 1: loose coupling via a neutral module).

Holds objects that both `main.py` and feature routers need, so routers do not
import from `main` (which would create an import cycle). Keep this tiny — only
truly shared framework singletons belong here.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single rate-limiter instance shared by the app and all routers.
limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter"]

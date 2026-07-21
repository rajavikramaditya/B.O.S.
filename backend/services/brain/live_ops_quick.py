"""Shim — live_ops_quick lives in tools/ (ADR-013). Do not add new logic here."""
from services.tools.live_ops_quick import (  # noqa: F401
    LOCAL_FAST_ACTIONS,
    try_live_ops_quick,
)

__all__ = ["LOCAL_FAST_ACTIONS", "try_live_ops_quick"]

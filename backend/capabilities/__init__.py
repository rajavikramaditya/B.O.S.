"""B.O.S. Capabilities Package v0.1

Provides generic platform capabilities:
- messaging
- scheduling
- memory
- automation
"""

from .base import BaseCapability, CapabilityResult, CapabilityRegistry
from .messaging import MessagingCapability
from .scheduling import SchedulingCapability
from .memory import MemoryCapability
from .automation import AutomationCapability

__all__ = [
    "BaseCapability",
    "CapabilityResult",
    "CapabilityRegistry",
    "MessagingCapability",
    "SchedulingCapability",
    "MemoryCapability",
    "AutomationCapability",
]

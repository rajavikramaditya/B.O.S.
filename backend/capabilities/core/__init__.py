"""B.O.S. Core Capabilities Package v1.0

Industry-neutral capabilities (contacts, tasks, events, memory, business context).
"""

from .catalog import build_core_capabilities, declare_reference_capabilities
from .provider_backed import ProviderBackedCapability

__all__ = ["build_core_capabilities", "declare_reference_capabilities", "ProviderBackedCapability"]

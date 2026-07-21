"""B.O.S. Capability Compatibility Layer v0.1

Provides the minimum compatibility surface for Frozen Core runtime/capability.py.
"""

from typing import Optional


class CapabilityRegistry:
    """Compatibility registry mapping Frozen Core calls to RuntimeCapabilityRegistry."""

    @classmethod
    def resolve_capability_for_action(cls, action: str) -> Optional[object]:
        """Resolves capability using the new RuntimeCapabilityRegistry."""
        from capabilities.registry import RuntimeCapabilityRegistry

        return RuntimeCapabilityRegistry.resolve_for_action(action)

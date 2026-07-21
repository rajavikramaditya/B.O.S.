"""B.O.S. Capability Engine v0.1

Stage 7 of Runtime Lifecycle: Maps plan steps to platform capabilities.
"""

from .contracts import ExecutionPlan, CapabilitySelection


class CapabilityEngine:
    """Selects platform capabilities for approved execution plans."""

    @staticmethod
    def select_capabilities(plan: ExecutionPlan) -> CapabilitySelection:
        from capabilities.base import CapabilityRegistry

        selected_caps = []
        mappings = {}
        for step in plan.steps:
            cap_instance = CapabilityRegistry.resolve_capability_for_action(step.action)
            cap_name = cap_instance.name if cap_instance else step.capability
            selected_caps.append(cap_name)
            mappings[cap_name] = step.action

        return CapabilitySelection(
            selected_capabilities=selected_caps,
            mappings=mappings,
        )

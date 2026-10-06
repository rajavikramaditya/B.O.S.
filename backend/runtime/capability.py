"""B.O.S. Capability Engine v1.0

Stage 7 of Runtime Lifecycle: Maps policy-approved plan steps to registered capabilities.
"""

from .contracts import CapabilitySelection, ExecutionPlan, PolicyDecision


class CapabilityEngine:
    """Selects platform capabilities for approved execution steps."""

    @staticmethod
    def select_capabilities(plan: ExecutionPlan, policy: PolicyDecision | None = None) -> CapabilitySelection:
        from capabilities.registry import RuntimeCapabilityRegistry

        steps = policy.allowed_steps if policy is not None else plan.steps
        selected, mappings = [], {}
        for step in steps:
            cap = RuntimeCapabilityRegistry.get(step.capability)
            if cap is None:
                continue
            selected.append(cap.name)
            mappings[str(step.step_id)] = {"capability": cap.name, "action": step.action, "version": cap.version}
        return CapabilitySelection(selected_capabilities=selected, mappings=mappings)

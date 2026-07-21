"""B.O.S. AI Orchestrator v0.1

Coordinates cognitive and reasoning engines for runtime requests.
Does NOT perform reasoning itself — coordinates reasoning.
"""

from typing import Any, Dict
from ..intent import IntentObject
from .orchestrator_state import OrchestratorState
from .orchestrator_context import OrchestratorContext
from .routing_strategy import RoutingStrategy


class AIOrchestrator:
    """Coordinates which reasoning, policy, memory, and graph engines participate in an execution run."""

    @classmethod
    def orchestrate(cls, intent: IntentObject, options: Dict[str, Any] | None = None) -> OrchestratorState:
        context = OrchestratorContext(intent=intent, options=options or {})
        engines = RoutingStrategy.determine_participating_engines(intent)

        state = OrchestratorState(
            participating_engines=engines,
            active_step="ROUTED",
            metadata={"goal": intent.goal, "actor_role": intent.actor_role},
        )
        state.mark_completed("ROUTING_DETERMINED")
        return state

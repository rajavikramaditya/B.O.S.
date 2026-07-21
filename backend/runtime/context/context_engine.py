"""B.O.S. Context Engine v0.1

Stage 3 of Runtime Lifecycle: Loads relevant memory, live snapshot, and system context.
"""

from ..contracts import NormalizedRequest, BusinessIntent, RuntimeContext


class ContextEngine:
    """Collects business and operational context required for reasoning."""

    @staticmethod
    def load_context(request: NormalizedRequest, intent: BusinessIntent) -> RuntimeContext:
        if request.role != "owner":
            return RuntimeContext()

        import services.brain.context_builder as context_builder
        import services.brain.live_state_snapshot as live_state_snapshot

        try:
            mem_str = context_builder.build_context_block()
        except Exception:
            mem_str = ""

        try:
            live_snap = live_state_snapshot.build_neena_live_state_snapshot()
        except Exception:
            live_snap = {}

        prefs = {}
        try:
            import services.brain.manager_state as manager_state
            if hasattr(manager_state, "get_manager_state"):
                prefs = manager_state.get_manager_state()
        except Exception:
            pass

        return RuntimeContext(
            memory_packet={},
            memory_context=mem_str or "",
            live_snapshot=live_snap if isinstance(live_snap, dict) else {},
            owner_preferences=prefs if isinstance(prefs, dict) else {},
        )

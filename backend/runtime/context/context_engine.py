"""B.O.S. Context Engine v0.1

Stage 3 of Runtime Lifecycle: Loads relevant memory, live snapshot, and system context.
"""

from ..contracts import NormalizedRequest, BusinessIntent, RuntimeContext


class ContextEngine:
    """Collects business and operational context required for reasoning."""

    # B-01: Bounded in-memory recency cache
    _recency_cache = {}

    @classmethod
    def _is_pronoun(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        val = value.lower().strip()
        pronouns = ["usko", "wahi", "usi", "usi customer", "previous customer", "kal wala", "last invoice", "last asset"]
        return any(p in val or val in p for p in pronouns)

    @classmethod
    def _resolve_pronoun(cls, key: str, value: str) -> str:
        if not isinstance(value, str):
            return value
        val = value.lower().strip()
        
        # Resolve by value content matching
        if "customer" in val or "person" in val or "usko" in val or "usi customer" in val or "previous customer" in val:
            return cls._recency_cache.get("customer", value)
        if "invoice" in val or "last invoice" in val:
            return cls._recency_cache.get("invoice", value)
        if "asset" in val or "last asset" in val or "wahi" in val or "kal wala" in val:
            if "customer" in key or "person" in key:
                return cls._recency_cache.get("customer", value)
            if "invoice" in key:
                return cls._recency_cache.get("invoice", value)
            return cls._recency_cache.get("asset", value)
            
        # Fallback by key
        if "customer" in key or "person" in key:
            return cls._recency_cache.get("customer", value)
        if "invoice" in key:
            return cls._recency_cache.get("invoice", value)
        if "asset" in key or "product" in key:
            return cls._recency_cache.get("asset", value)
            
        return cls._recency_cache.get(key, value)

    @classmethod
    def load_context(cls, request: NormalizedRequest, intent: BusinessIntent) -> RuntimeContext:
        # Update recency cache with concrete entities
        if intent and intent.entities:
            for k, v in list(intent.entities.items()):
                if v and not cls._is_pronoun(str(v)):
                    v_str = str(v)
                    if "customer" in k or "person" in k or "recipient" in k:
                        cls._recency_cache["customer"] = v_str
                    elif "invoice" in k:
                        cls._recency_cache["invoice"] = v_str
                    elif "asset" in k or "product" in k:
                        cls._recency_cache["asset"] = v_str
                    cls._recency_cache[k] = v_str

        # Update recency cache with concrete slots
        if intent and intent.slots:
            for k, v in list(intent.slots.items()):
                if v and not cls._is_pronoun(str(v)):
                    v_str = str(v)
                    if "customer" in k or "person" in k or "recipient" in k:
                        cls._recency_cache["customer"] = v_str
                    elif "invoice" in k:
                        cls._recency_cache["invoice"] = v_str
                    elif "asset" in k or "product" in k:
                        cls._recency_cache["asset"] = v_str
                    cls._recency_cache[k] = v_str

        # Resolve pronouns in entities
        if intent and intent.entities:
            for k, v in list(intent.entities.items()):
                if v and cls._is_pronoun(str(v)):
                    resolved = cls._resolve_pronoun(k, str(v))
                    intent.entities[k] = resolved

        # Resolve pronouns in slots
        if intent and intent.slots:
            for k, v in list(intent.slots.items()):
                if v and cls._is_pronoun(str(v)):
                    resolved = cls._resolve_pronoun(k, str(v))
                    intent.slots[k] = resolved

        if request.role != "owner":
            return RuntimeContext(entity_recency_cache=dict(cls._recency_cache))

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
            entity_recency_cache=dict(cls._recency_cache),
        )


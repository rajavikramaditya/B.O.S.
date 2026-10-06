"""B.O.S. Context Engine v1.0

Stage 2 of Runtime Lifecycle (ADR-008): Loads memory, business profile, live snapshot
and the capability catalog before the request is interpreted.

The B-01 recency cache below is kept for compatibility (KEEP). It only runs when an
intent is passed in; the AI Understanding stage now resolves references from history.
"""

from typing import Optional

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
    def load_context(cls, request: NormalizedRequest, intent: Optional[BusinessIntent] = None) -> RuntimeContext:
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

        return cls._load_business_context(request)

    @classmethod
    def _load_business_context(cls, request: NormalizedRequest) -> RuntimeContext:
        """Assemble memory, business profile, live snapshot and the plannable capability catalog.

        Everything is fetched through capabilities, so the Runtime never touches a store directly.
        """
        from capabilities.base.capability_context import CapabilityContext
        from capabilities.resolver import CapabilityResolver
        from ..cognition import RuntimeCognition

        ctx = CapabilityContext(module_id="runtime", correlation_id=request.request_id)

        history = []
        if request.conversation_id:
            mem = CapabilityResolver.execute(
                "conversation_memory", "history", {"conversation_id": request.conversation_id, "limit": 24}, ctx
            )
            if mem.success:
                history = mem.data.get("messages", [])

        profile, snapshot, mode = {}, {}, "autopilot"
        biz = CapabilityResolver.execute("business_context", "snapshot", {}, ctx)
        if biz.success:
            profile = biz.data.get("profile", {})
            snapshot = biz.data.get("snapshot", {})
            mode = biz.data.get("autopilot_mode", mode)

        actor_profile = {}
        if request.actor_ref:
            found = CapabilityResolver.execute("contacts", "find_contact", {"id": request.actor_ref}, ctx)
            if found.success:
                actor_profile = found.data.get("contact") or {}

        return RuntimeContext(
            memory_packet={"history_messages": len(history)},
            live_snapshot=snapshot,
            owner_preferences={"autopilot_mode": mode} if request.role == "owner" else {},
            entity_recency_cache=dict(cls._recency_cache),
            business_profile=profile,
            business_snapshot=snapshot,
            conversation_history=history,
            capability_catalog=RuntimeCognition.capability_catalog(),
            actor_profile=actor_profile,
            autopilot_mode=mode,
        )

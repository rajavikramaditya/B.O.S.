"""B.O.S. Runtime Event Bus v0.1

Central event bus publishing events and invoking subscribed handlers asynchronously or synchronously.
"""

import uuid
from typing import Callable, Dict, List, Any
from .event import RuntimeEvent
from .event_types import EventType
from .subscriptions import EventSubscription


class RuntimeEventBus:
    """Publish-subscribe event bus driving event-reactive execution."""

    _subscribers: Dict[str, List[EventSubscription]] = {}
    _event_history: List[RuntimeEvent] = []

    @classmethod
    def subscribe(
        cls, event_type: EventType | str, handler: Callable[[RuntimeEvent], Any]
    ) -> str:
        etype = event_type.value if hasattr(event_type, "value") else str(event_type)
        if etype not in cls._subscribers:
            cls._subscribers[etype] = []

        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        subscription = EventSubscription(
            subscription_id=sub_id,
            event_type=etype,
            handler=handler,
        )
        cls._subscribers[etype].append(subscription)
        return sub_id

    @classmethod
    def unsubscribe(cls, subscription_id: str) -> bool:
        for etype, subs in cls._subscribers.items():
            for i, sub in enumerate(subs):
                if sub.subscription_id == subscription_id:
                    subs.pop(i)
                    return True
        return False

    @classmethod
    def publish(cls, event: RuntimeEvent) -> List[Any]:
        cls._event_history.append(event)
        etype = event.get_event_type_str()

        results = []
        # Dispatch to specific handlers
        handlers = cls._subscribers.get(etype, []) + cls._subscribers.get("*", [])
        for sub in handlers:
            try:
                res = sub.handler(event)
                results.append(res)
            except Exception as ex:
                results.append({"error": str(ex)})

        return results

    @classmethod
    def get_event_history(cls, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in cls._event_history[-limit:]]

    @classmethod
    def clear(cls) -> None:
        cls._subscribers.clear()
        cls._event_history.clear()

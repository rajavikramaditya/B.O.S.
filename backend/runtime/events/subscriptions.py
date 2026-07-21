"""B.O.S. Runtime Event Subscriptions v0.1

Subscription handlers for event-driven runtime reaction.
"""

from dataclasses import dataclass
from typing import Callable, Any
from .event import RuntimeEvent


@dataclass
class EventSubscription:
    subscription_id: str
    event_type: str
    handler: Callable[[RuntimeEvent], Any]

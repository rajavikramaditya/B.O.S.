"""B.O.S. Base Adapter v0.1

Abstract Base Class for external system integration adapters.
Adapters translate platform capability requests into provider-specific calls.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from .adapter_contracts import AdapterRequest, AdapterResponse, AdapterStatus


class BaseAdapter(ABC):
    """Abstract base class for all B.O.S. external system adapters."""

    def __init__(self, name: str, channel_type: str):
        self.name = name
        self.channel_type = channel_type
        self.status = AdapterStatus.DISCONNECTED

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def execute_request(self, request: AdapterRequest) -> AdapterResponse:
        pass

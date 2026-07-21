"""B.O.S. Base Configuration Abstract Class v0.1

Abstract Base Class for all normalized configuration objects in B.O.S.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from .configuration_metadata import ConfigurationMetadata


class BaseConfiguration(ABC):
    """Abstract base class for platform configuration objects."""

    def __init__(self, metadata: ConfigurationMetadata, values: Dict[str, Any] | None = None):
        self.metadata = metadata
        self.values = values or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.values)

    @abstractmethod
    def validate(self) -> bool:
        """Validate configuration schema and required settings."""
        pass

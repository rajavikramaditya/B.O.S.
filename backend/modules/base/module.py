"""B.O.S. Abstract Base Module v0.1

Abstract Base Class for all installable business modules.
Modules inherit ONLY from this contract. Zero business-specific logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from .module_lifecycle import ModuleLifecycle
from .module_metadata import ModuleMetadata
from .module_state import ModuleState
from .module_context import ModuleContext
from .manifest import ModuleManifest


class BaseModule(ABC):
    """Abstract base class for installable B.O.S. business modules."""

    def __init__(self, manifest: ModuleManifest):
        self.manifest = manifest
        self.metadata = ModuleMetadata(
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            description=manifest.description,
        )
        self.state = ModuleState(status=ModuleLifecycle.UNLOADED)
        self.context: ModuleContext | None = None

    @abstractmethod
    def initialize(self, context: ModuleContext) -> bool:
        """Called during module loading to inject context and register components."""
        pass

    @abstractmethod
    def enable(self) -> bool:
        """Called when module is enabled."""
        pass

    @abstractmethod
    def disable(self) -> bool:
        """Called when module is disabled."""
        pass

    @abstractmethod
    def unload(self) -> bool:
        """Called when module is unloaded."""
        pass

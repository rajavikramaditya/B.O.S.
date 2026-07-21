"""B.O.S. Base Capability v0.1

Abstract Base Class for all platform capabilities.

Capabilities describe WHAT the platform can do.
Providers describe HOW capabilities are executed.

Capabilities must remain completely provider-independent.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .capability_context import CapabilityContext
from .capability_lifecycle import CapabilityLifecycle
from .capability_metadata import CapabilityMetadata
from .capability_result import CapabilityResult


class BaseCapability(ABC):
    """Abstract base class for all B.O.S. platform capabilities.

    Subclasses define WHAT the platform can do.
    The execution of HOW is delegated to Providers via ProviderResolver.

    Rules:
    - Never import specific provider classes.
    - Never call services.* directly.
    - Always return CapabilityResult.
    - Always accept CapabilityContext.
    """

    def __init__(self, metadata: CapabilityMetadata):
        self.metadata = metadata
        self.metadata.lifecycle = CapabilityLifecycle.REGISTERED

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def category(self) -> str:
        return self.metadata.category

    @property
    def lifecycle(self) -> CapabilityLifecycle:
        return self.metadata.lifecycle

    @abstractmethod
    def supported_actions(self) -> List[str]:
        """Return the list of action names this capability supports."""
        pass

    @abstractmethod
    def execute(
        self, action: str, params: Dict[str, Any], context: CapabilityContext
    ) -> CapabilityResult:
        """Execute capability action with given params and context.

        Must return CapabilityResult in all cases — never raise unhandled exceptions.
        """
        pass

    def execute_safe(
        self, action: str, params: Dict[str, Any], context: CapabilityContext
    ) -> CapabilityResult:
        """Safe wrapper around execute() — catches all exceptions."""
        start = time.time()
        try:
            result = self.execute(action, params, context)
            result.execution_time_ms = (time.time() - start) * 1000
            result.correlation_id = result.correlation_id or context.correlation_id
            return result
        except Exception as ex:
            return CapabilityResult(
                success=False,
                capability_name=self.name,
                action=action,
                error=f"Capability '{self.name}' raised unexpected exception: {str(ex)}",
                correlation_id=context.correlation_id,
                execution_time_ms=(time.time() - start) * 1000,
            )

    def supports_action(self, action: str) -> bool:
        """Check if this capability supports a given action."""
        return action in self.supported_actions()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "lifecycle": self.lifecycle.value,
            "supported_actions": self.supported_actions(),
            "metadata": self.metadata.to_dict(),
        }

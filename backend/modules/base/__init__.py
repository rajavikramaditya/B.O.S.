"""B.O.S. Module Base Contracts Package v0.1

Provides ModuleLifecycle, ModuleMetadata, ModuleState, ModuleContext, ModuleManifest, and BaseModule.
"""

from .module_lifecycle import ModuleLifecycle
from .module_metadata import ModuleMetadata
from .module_state import ModuleState
from .module_context import ModuleContext
from .manifest import ModuleManifest
from .module import BaseModule

__all__ = [
    "ModuleLifecycle",
    "ModuleMetadata",
    "ModuleState",
    "ModuleContext",
    "ModuleManifest",
    "BaseModule",
]

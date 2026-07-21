"""B.O.S. Runtime Capability Registry v0.1

Central registry for all platform capabilities.

Responsibilities:
- Register capabilities by name
- Resolve capabilities by name, category, or version
- Enable / Disable capabilities
- Category index for discovery
- Dependency validation
- No vendor-specific knowledge
"""

from typing import Any, Dict, List, Optional

from .base.base_capability import BaseCapability
from .base.capability_lifecycle import CapabilityLifecycle
from .events import CapabilityEventPublisher, CapabilityEventType


class RuntimeCapabilityRegistry:
    """Central runtime registry for all platform capabilities."""

    # Primary registry: name (lowercase) → BaseCapability
    _capabilities: Dict[str, BaseCapability] = {}

    # Category index: category → [capability names]
    _category_index: Dict[str, List[str]] = {}

    # Version index: name → version → BaseCapability
    _version_index: Dict[str, Dict[str, BaseCapability]] = {}

    # Enable/disable state
    _enabled: Dict[str, bool] = {}

    # --------------------------------------------------------------------------
    # Registration
    # --------------------------------------------------------------------------

    @classmethod
    def register(cls, capability: BaseCapability) -> None:
        """Register a capability in the runtime registry."""
        key = capability.name.lower()

        cls._capabilities[key] = capability
        cls._enabled[key] = True
        capability.metadata.lifecycle = CapabilityLifecycle.REGISTERED

        # Category index
        cat = capability.category.lower()
        if cat not in cls._category_index:
            cls._category_index[cat] = []
        if key not in cls._category_index[cat]:
            cls._category_index[cat].append(key)

        # Version index
        if key not in cls._version_index:
            cls._version_index[key] = {}
        cls._version_index[key][capability.version] = capability

        CapabilityEventPublisher.publish(
            CapabilityEventType.CAPABILITY_REGISTERED,
            capability.name,
            {"version": capability.version, "category": capability.category},
        )

    # --------------------------------------------------------------------------
    # Resolution
    # --------------------------------------------------------------------------

    @classmethod
    def get(cls, name: str) -> Optional[BaseCapability]:
        """Resolve an enabled capability by name."""
        key = name.lower()
        if cls._enabled.get(key, False):
            return cls._capabilities.get(key)
        return None

    @classmethod
    def get_version(cls, name: str, version: str) -> Optional[BaseCapability]:
        """Resolve a specific version of a capability."""
        versions = cls._version_index.get(name.lower(), {})
        return versions.get(version)

    @classmethod
    def resolve_by_category(cls, category: str) -> List[BaseCapability]:
        """Return all enabled capabilities in a given category."""
        cat = category.lower()
        names = cls._category_index.get(cat, [])
        return [
            cls._capabilities[n]
            for n in names
            if cls._enabled.get(n, False) and n in cls._capabilities
        ]

    @classmethod
    def resolve_for_action(cls, action: str) -> Optional[BaseCapability]:
        """Find the first enabled capability that supports a given action."""
        for name, cap in cls._capabilities.items():
            if cls._enabled.get(name, False) and cap.supports_action(action):
                return cap
        return None

    # --------------------------------------------------------------------------
    # Enable / Disable
    # --------------------------------------------------------------------------

    @classmethod
    def enable(cls, name: str) -> bool:
        """Enable a registered capability."""
        key = name.lower()
        if key in cls._capabilities:
            cls._enabled[key] = True
            cls._capabilities[key].metadata.lifecycle = CapabilityLifecycle.ENABLED
            CapabilityEventPublisher.publish(CapabilityEventType.CAPABILITY_ENABLED, name)
            return True
        return False

    @classmethod
    def disable(cls, name: str) -> bool:
        """Disable a registered capability."""
        key = name.lower()
        if key in cls._capabilities:
            cls._enabled[key] = False
            cls._capabilities[key].metadata.lifecycle = CapabilityLifecycle.DISABLED
            CapabilityEventPublisher.publish(CapabilityEventType.CAPABILITY_DISABLED, name)
            return True
        return False

    # --------------------------------------------------------------------------
    # Discovery
    # --------------------------------------------------------------------------

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        """List all registered capabilities with their metadata."""
        return [cap.to_dict() for cap in cls._capabilities.values()]

    @classmethod
    def list_enabled(cls) -> List[Dict[str, Any]]:
        """List all currently enabled capabilities."""
        return [
            cap.to_dict()
            for name, cap in cls._capabilities.items()
            if cls._enabled.get(name, False)
        ]

    @classmethod
    def list_categories(cls) -> List[str]:
        """Return all registered capability categories."""
        return list(cls._category_index.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name.lower() in cls._capabilities

    @classmethod
    def is_enabled(cls, name: str) -> bool:
        return cls._enabled.get(name.lower(), False)

    # --------------------------------------------------------------------------
    # Dependency Validation
    # --------------------------------------------------------------------------

    @classmethod
    def validate_dependencies(cls, capability: BaseCapability) -> List[str]:
        """Validate that all declared capability dependencies are registered.

        Returns a list of missing dependency names (empty = all satisfied).
        """
        missing = []
        for dep in capability.metadata.dependencies:
            if not cls.is_registered(dep):
                missing.append(dep)
        return missing

    # --------------------------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------------------------

    @classmethod
    def clear(cls) -> None:
        """Clear all registered capabilities. Used in tests only."""
        cls._capabilities.clear()
        cls._category_index.clear()
        cls._version_index.clear()
        cls._enabled.clear()

"""B.O.S. Capability Policy Manager v0.1

Validates capability execution against platform policies.

Checks:
- Allowed providers
- Denied providers
- Permission requirements
- Tenant restrictions
- Feature flag requirements
"""

from typing import Any, Dict, List, Optional, Tuple

from .base.capability_context import CapabilityContext
from .base.capability_metadata import CapabilityMetadata


class CapabilityPolicyManager:
    """Validates capability execution requests against platform policies."""

    # Class-level policy configuration
    _denied_providers: Dict[str, List[str]] = {}        # capability_name → [denied_provider_names]
    _allowed_providers: Dict[str, List[str]] = {}       # capability_name → [allowed_provider_names] (empty = all)
    _required_permissions: Dict[str, List[str]] = {}    # capability_name → [required_permissions]
    _tenant_restrictions: Dict[str, List[str]] = {}     # capability_name → [allowed_tenant_ids] (empty = all)
    _required_flags: Dict[str, List[str]] = {}          # capability_name → [required_feature_flags]

    # --------------------------------------------------------------------------
    # Policy Configuration
    # --------------------------------------------------------------------------

    @classmethod
    def set_denied_providers(cls, capability_name: str, providers: List[str]) -> None:
        """Block specific providers for a capability."""
        cls._denied_providers[capability_name.lower()] = [p.lower() for p in providers]

    @classmethod
    def set_allowed_providers(cls, capability_name: str, providers: List[str]) -> None:
        """Restrict a capability to specific providers only."""
        cls._allowed_providers[capability_name.lower()] = [p.lower() for p in providers]

    @classmethod
    def set_required_permissions(cls, capability_name: str, permissions: List[str]) -> None:
        """Require specific permissions for capability execution."""
        cls._required_permissions[capability_name.lower()] = permissions

    @classmethod
    def set_tenant_restrictions(cls, capability_name: str, tenant_ids: List[str]) -> None:
        """Restrict a capability to specific tenants."""
        cls._tenant_restrictions[capability_name.lower()] = tenant_ids

    @classmethod
    def set_required_flags(cls, capability_name: str, flags: List[str]) -> None:
        """Require specific feature flags to be active for execution."""
        cls._required_flags[capability_name.lower()] = flags

    # --------------------------------------------------------------------------
    # Validation
    # --------------------------------------------------------------------------

    @classmethod
    def validate(
        cls,
        capability_name: str,
        context: CapabilityContext,
        metadata: Optional[CapabilityMetadata] = None,
        provider_name: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validate a capability execution request.

        Returns:
            (True, "") if allowed.
            (False, reason) if blocked.
        """
        key = capability_name.lower()

        # 1. Feature flag validation
        required_flags = cls._required_flags.get(key, [])
        for flag in required_flags:
            if not context.has_flag(flag):
                return False, f"Feature flag '{flag}' is required but not active."

        # 2. Tenant restriction validation
        allowed_tenants = cls._tenant_restrictions.get(key, [])
        if allowed_tenants and context.tenant_id not in allowed_tenants:
            return False, (
                f"Capability '{capability_name}' is not available for tenant '{context.tenant_id}'."
            )

        # 3. Permission validation (from metadata + policy)
        required_permissions: List[str] = []
        if metadata:
            required_permissions.extend(metadata.permissions)
        required_permissions.extend(cls._required_permissions.get(key, []))

        granted_permissions: List[str] = context.get_config("permissions", [])
        for perm in required_permissions:
            if perm not in granted_permissions:
                return False, f"Required permission '{perm}' is not granted in context."

        # 4. Provider validation (only if a specific provider is named)
        if provider_name:
            pname = provider_name.lower()

            # Denied providers
            denied = cls._denied_providers.get(key, [])
            if pname in denied:
                return False, f"Provider '{provider_name}' is denied for capability '{capability_name}'."

            # Allowed providers (if allowlist is non-empty, must be in it)
            allowed = cls._allowed_providers.get(key, [])
            if allowed and pname not in allowed:
                return False, (
                    f"Provider '{provider_name}' is not in the allowed list for capability '{capability_name}'."
                )

        return True, ""

    @classmethod
    def is_provider_allowed(cls, capability_name: str, provider_name: str) -> bool:
        """Quick check: is a given provider allowed for this capability?"""
        allowed, _ = cls.validate(
            capability_name,
            CapabilityContext(),  # empty context for provider-only check
            provider_name=provider_name,
        )
        return allowed

    # --------------------------------------------------------------------------
    # Introspection
    # --------------------------------------------------------------------------

    @classmethod
    def get_policy_summary(cls, capability_name: str) -> Dict[str, Any]:
        """Return the full policy configuration for a capability."""
        key = capability_name.lower()
        return {
            "capability_name": capability_name,
            "denied_providers": cls._denied_providers.get(key, []),
            "allowed_providers": cls._allowed_providers.get(key, []),
            "required_permissions": cls._required_permissions.get(key, []),
            "tenant_restrictions": cls._tenant_restrictions.get(key, []),
            "required_flags": cls._required_flags.get(key, []),
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all policies. Used in tests only."""
        cls._denied_providers.clear()
        cls._allowed_providers.clear()
        cls._required_permissions.clear()
        cls._tenant_restrictions.clear()
        cls._required_flags.clear()

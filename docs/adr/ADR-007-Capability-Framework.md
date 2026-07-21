# ADR-007: Capability Framework Architecture

## Context
B.O.S. Core v1.0 is frozen. The platform needed a formal, layered Capability Framework that:
1. Defines WHAT the platform can do (Capabilities)
2. Delegates HOW to Providers via ProviderResolver
3. Never exposes vendor-specific code to Business Modules
4. Coexists safely with the legacy capability layer without breaking Frozen Core consumers

## Problem
- Legacy `backend/capabilities/` contained flat, radio-specific capabilities calling `services.brain.*` and `services.tools.*` directly — architecture violation.
- `backend/runtime/capability.py` (Frozen Core) consumed the legacy `CapabilityRegistry` from `base.py`.
- No formal lifecycle, scope, metadata, policy, or event system existed.

## Decision
We implement the Capability Framework under `backend/capabilities/base/` and companion modules:

1. **Base Capability Contract** (`backend/capabilities/base/`):
   - `BaseCapability(ABC)`: abstract execute(action, params, context) with execute_safe() wrapper
   - `CapabilityMetadata`: name, version, category, required_providers, permissions, scope, lifecycle
   - `CapabilityContext`: tenant_id, module_id, correlation_id, feature_flags, configuration
   - `CapabilityResult`: normalized output envelope with success, data, error, provider_used, execution_time_ms
   - `CapabilityScope`: GLOBAL, MODULE, TENANT, SYSTEM
   - `CapabilityLifecycle`: UNREGISTERED, REGISTERED, ENABLED, DISABLED, DEPRECATED

2. **Capability Manifest** (`backend/capabilities/base/manifest.py`):
   - Parses `capability.json` and `capability.yaml`
   - Converts to CapabilityMetadata for runtime registration

3. **Runtime Capability Registry** (`backend/capabilities/registry.py`):
   - Central registry with category index and version index
   - Enable/disable, dependency validation, discovery

4. **Capability Resolver** (`backend/capabilities/resolver.py`):
   - 4-step pipeline: resolve → validate action → validate policies → execute
   - Publishes lifecycle events at each step

5. **Capability Policy Manager** (`backend/capabilities/policies.py`):
   - Allowed/denied providers, permission validation, tenant restrictions, feature flag gates

6. **Capability Events** (`backend/capabilities/events.py`):
   - CapabilityRegistered, CapabilityEnabled, CapabilityDisabled, CapabilityResolved, CapabilityFailed
   - Graceful degradation when EventBus is not initialized

7. **Reference Capabilities** (`backend/capabilities/reference/`):
   - `GenerateTextCapability` (ai category) → delegates to text_generation provider
   - `StoreDocumentCapability` (storage category) → delegates to document_storage provider
   - `SendMessageCapability` (messaging category) → delegates to messaging provider

8. **Legacy Compatibility Bridge**:
   - Legacy `base.py`, `messaging.py`, `scheduling.py`, `memory.py`, `automation.py` load legacy base via `importlib.util` to avoid name conflict with the new `base/` sub-package
   - `runtime/capability.py` (Frozen Core) continues to work unchanged

## Status
ACCEPTED

## Consequences
- Business Modules know only CapabilityResolver — never ProviderResolver, never services.*
- Capabilities know only contracts — never specific vendor APIs
- Providers execute implementations — only the Provider Layer knows external APIs
- Legacy capabilities coexist safely with new framework (KEEP rule respected)
- All 41 Sprint-12 tests pass

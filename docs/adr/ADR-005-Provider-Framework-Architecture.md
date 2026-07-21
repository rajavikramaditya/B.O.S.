# ADR-005: Provider Framework Architecture

## Context
Following the permanent Core Freeze of B.O.S. Core v1.0, the platform requires a plug-and-play Provider Framework allowing external technology infrastructure (LLMs, Databases, Messaging Gateways, Speech Synthesizers, Storage engines) to plug into the platform without modifying the frozen Core Kernel or Runtime.

## Decision
We implement the Provider Framework under `backend/providers/`:
1. **Base Provider Contract**: All technology providers inherit from `BaseProvider` (`backend/providers/base/base_provider.py`), declaring `ProviderMetadata`, `ProviderContext`, `ProviderState`, `ProviderLifecycle`, and `ProviderScope`.
2. **Provider Manifest Parser**: `ProviderManifest` (`backend/providers/base/manifest.py`) parses `provider.json` and `provider.yaml` specification files.
3. **Runtime Provider Registry**: `RuntimeProviderRegistry` (`backend/providers/registry.py`) manages provider registration, capability indexing, activation state, priority sorting, replacement, and unregistration.
4. **Provider Loader**: `ProviderLoader` (`backend/providers/loader.py`) validates manifests, instantiates providers, injects service context, and registers active instances.
5. **Provider Resolver**: `ProviderResolver` (`backend/providers/resolver.py`) dynamically selects the best provider for a capability based on capability match, health status, and priority (no hardcoding).
6. **Provider Health & Diagnostics**: `ProviderHealth` (`backend/providers/health.py`) reports `READY`, `LIVE`, `DEGRADED`, and `UNAVAILABLE` status.
7. **Provider Lifecycle Events**: `ProviderEventPublisher` (`backend/providers/events.py`) emits `ProviderRegistered`, `ProviderLoaded`, `ProviderEnabled`, `ProviderDisabled`, `ProviderHealthChanged`, and `ProviderRemoved` to `RuntimeEventBus`.
8. **Reference Providers**: `LocalEchoProvider` (priority 10) and `MemoryEchoProvider` (priority 20) in `backend/providers/reference/` validate dynamic resolution, priority selection, and fallback execution.

## Status
ACCEPTED

## Consequences
- Core Kernel, Runtime, Service Container, and Execution Pipeline remain 100% frozen and unmodified.
- Infrastructure technologies (Gemini, OpenAI, Claude, Ollama, PostgreSQL, SQLite, Redis, S3, Twilio) can be added or swapped seamlessly as standalone providers.

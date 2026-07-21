# ADR-002: Service Layer & Dependency Injection Container

## Context
As B.O.S. scales across platform capabilities, external adapters, and installable modules, components require a standardized mechanism to discover, resolve, and inject dependencies without hardcoding service instantiations or creating hidden tight couplings.

## Decision
We implement a generic Service Layer under `backend/core/services/`:
1. **Service Contract**: All platform services inherit from `BaseService` (`backend/core/services/base_service.py`), declaring `ServiceMetadata`, `ServiceContext`, `ServiceScope` (Singleton, Transient, Scoped), and `ServiceLifecycle`.
2. **Runtime Service Registry**: `RuntimeServiceRegistry` manages service registration, resolution, replacement, and unregistration dynamically.
3. **Dependency Injection Container**: `ServiceContainer` handles recursive dependency resolution, constructor injection, lazy initialization, and circular dependency detection (`CircularDependencyError`).
4. **Service Discovery Facade**: `ServiceDiscovery` provides a unified entry point for Modules, Runtime, Graphs, Capabilities, and Adapters to discover platform services safely.
5. **Health Diagnostics**: `ServiceHealth` reports liveness, readiness, and state diagnostics for system monitoring.
6. **Reference Implementation**: `ClockService` (`backend/core/services/reference/clock_service.py`) proves registration, DI resolution, health checks, and service replacement.

## Status
ACCEPTED

## Consequences
- Eliminates manual component wiring and hidden dependencies across platform layers.
- Prepares the infrastructure for the plug-and-play Provider Layer (Sprint-9).
- Ensures service replacements (e.g. mock services during testing or alternative implementations) occur seamlessly without modifying consuming code.

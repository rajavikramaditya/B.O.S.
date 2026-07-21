# B.O.S. Module Registry

## Overview
This document is the single source of truth for all software modules, packages, engines, and layers within the Business Operating System (B.O.S.).

> [!IMPORTANT]
> **B.O.S. Core v1.0 is FROZEN.** Sections 1, 2, 3, 4, and 5 represent the locked Core platform core.

---

# 1. BOS Core & Cognitive Kernel (FROZEN)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `runtime/intent` | Runtime Engine | Intent classification & intent object creation | Contracts | Orchestrator, RuntimeEngine | Stable |
| `runtime/orchestrator` | Cognitive Kernel | Cognitive routing & engine orchestration | IntentEngine | RuntimeEngine | Stable |
| `runtime/reasoning` | Cognitive Kernel | Domain reasoning across business, knowledge, memory, capability | IntentObject, Context | Orchestrator, RuntimeEngine | Stable |
| `runtime/goals` | Cognitive Kernel | Business goal breakdown, milestone tracking & progress metrics | None | Orchestrator, RuntimeEngine | Stable |
| `runtime/decision` | Runtime Engine | Risk scoring, approval checks & fallback strategy | IntentObject | PolicyEngine, RuntimeEngine | Stable |
| `runtime/policy` | Governance Layer | Multi-policy evaluation (Security, Approval, Permissions, Business, Execution) | Contracts | DecisionEngine, RuntimeEngine | Stable |
| `runtime/planner` | Runtime Engine | WorkflowGraph plan generation | Contracts, Capabilities | PlanExecutor, RuntimeEngine | Stable |
| `runtime/plan_executor` | Runtime Engine | Step-by-step plan execution, pause/resume, checkpointing, rollback | AdapterRouter, Contracts | RuntimeEngine | Stable |
| `runtime/registry` | Capability Layer | Platform capability registration and lookup | CapabilityMetadata | CapabilityEngine, PlanExecutor | Stable |
| `runtime/workflow_memory` | Memory Layer | Past workflow execution history and pattern recall | WorkflowGraph | ReasoningEngine, GraphOrchestrator | Stable |
| `core/graph` | Graph Layer | Independent Graph Layer (`business`, `knowledge`, `capability`, `graph_orchestrator`) | Entities | ReasoningEngine, RuntimeEngine | Stable |

---

# 2. Execution Pipeline & Command Bus (FROZEN)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `core/execution/command` | Execution Layer | Command contract (`Command`, `CommandMetadata`, `CommandContext`, `CommandResult`, `ExecutionState`) | None | Capabilities, Modules | Stable |
| `core/execution/command_bus` | Execution Layer | Central command dispatch, queueing, execution & status tracking | Command, ExecutionPipeline | Capabilities, Modules | Stable |
| `core/execution/pipeline` | Execution Layer | 6-stage execution pipeline (`Validate → Authorize → Prepare → Execute → Verify → Finalize`) | PolicyEngineV2, MiddlewareChain | CommandBus | Stable |
| `core/execution/middleware` | Execution Layer | Middleware chain for Logging, Metrics, Tracing, and Policy | Command | ExecutionPipeline | Stable |
| `core/execution/transaction` | Execution Layer | Transaction context tracking `correlation_id` and nested execution runs | None | CommandBus, Pipeline | Stable |
| `core/execution/events` | Execution Layer | Lifecycle event publisher for command executions | RuntimeEventBus | ExecutionPipeline | Stable |
| `core/execution/reference/echo_command` | Reference Command | Reference command validating pipeline execution (`EchoCommand`) | Command | CommandBus | Stable |

---

# 3. Generic Service Layer & Dependency Injection (FROZEN)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `core/services/base` | Service Layer | Service contract (`BaseService`, `ServiceMetadata`, `ServiceContext`, `ServiceScope`, `ServiceLifecycle`) | None | System Services | Stable |
| `core/services/registry` | Service Layer | Runtime service registration, resolution, replacement & unregistration | BaseService, ServiceEventPublisher | ServiceContainer, Discovery | Stable |
| `core/services/container` | Service Layer | Constructor injection, lazy resolution, dependency graph & circular dependency detection | RuntimeServiceRegistry | ServiceDiscovery | Stable |
| `core/services/discovery` | Service Layer | Public service discovery facade for Modules, Runtime, Graphs, Capabilities, Adapters | ServiceContainer, ServiceRegistry | Platform Layers | Stable |
| `core/services/events` | Service Layer | Event publisher for service lifecycle transitions | RuntimeEventBus | ServiceRegistry | Stable |
| `core/services/health` | Service Layer | Readiness, liveness, and diagnostic status reporting | None | BaseService, System Monitoring | Stable |
| `core/services/reference/clock_service` | Reference Service | Reference system service (`ClockService`) | BaseService, ServiceMetadata | ServiceContainer | Stable |

---

# 4. Module Extension Framework (FROZEN)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `modules/base` | Extension Layer | Base Module contract (`BaseModule`, `ModuleMetadata`, `ModuleState`, `ModuleContext`, `ModuleLifecycle`, `ModuleManifest`) | None | Business Modules | Stable |
| `modules/registry` | Extension Layer | Dynamic runtime module registry & lifecycle state management | BaseModule, ModuleEventPublisher | RuntimeEngine, Loader | Stable |
| `modules/loader` | Extension Layer | Module instantiation, manifest validation, dependency resolution & context injection | ModuleManifest, ModuleSandbox | RuntimeEngine | Stable |
| `modules/sandbox` | Extension Layer | Sandbox isolation & capability/policy extension registration | CapabilityRegistry, PolicyEngineV2 | ModuleLoader | Stable |
| `modules/events` | Extension Layer | Lifecycle event publisher for module transitions | RuntimeEventBus | ModuleRegistry, Kernel | Stable |
| `modules/reference/notes_module` | Reference Module | Minimal reference module proving extension architecture (`NotesModule`) | BaseModule, ModuleManifest | ModuleLoader | Stable |

---

# 5. Adapters & Integrations (FROZEN)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `adapters/messaging` | Adapter Layer | Channel adapters for WhatsApp, Telegram, Email | BaseAdapter | AdapterRouter | Stable |
| `adapters/system` | Adapter Layer | System adapters for Calendar, Voice, Payments, Storage | BaseAdapter | AdapterRouter | Stable |
| `adapters/router` | Adapter Layer | Capability action routing to registered adapters | AdapterRegistry | StepRunner, PlanExecutor | Stable |

---

# 6. Provider Framework (Infrastructure Integration Layer)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `providers/base` | Provider Layer | Base Provider contract (`BaseProvider`, `ProviderMetadata`, `ProviderContext`, `ProviderState`, `ProviderLifecycle`, `ProviderScope`, `ProviderManifest`) | None | Technology Providers | Stable |
| `providers/registry` | Provider Layer | Dynamic runtime provider registry, priority resolution & capability indexing | BaseProvider, ProviderEventPublisher | ProviderResolver | Stable |
| `providers/loader` | Provider Layer | Manifest validation (`provider.json`/`yaml`), instantiation & context injection | ProviderManifest, RuntimeProviderRegistry | Platform Startup | Stable |
| `providers/resolver` | Provider Layer | Dynamic provider resolution based on capability, health, and priority | RuntimeProviderRegistry, ProviderHealth | AdapterRouter, Capabilities | Stable |
| `providers/health` | Provider Layer | Liveness, readiness, degraded, and diagnostic status reporting | BaseProvider | ProviderResolver | Stable |
| `providers/events` | Provider Layer | Event publisher for provider lifecycle state transitions | RuntimeEventBus | ProviderRegistry | Stable |
| `providers/reference` | Reference Providers | Reference dummy providers (`LocalEchoProvider`, `MemoryEchoProvider`) | BaseProvider | ProviderResolver | Stable |

---

# 7. Legacy Modules (Read-Only Knowledge Sources)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `services/broadcast` | Business Module | AzuraCast streaming & radio broadcast management | AzuraCast Client | Radio Module | Legacy |
| `services/content` | Content Service | Regional news scraper | Requests | Knowledge Ingestion | Legacy |
| `services/safety` | Legacy Security | Legacy Safety Kernel & confirm logic | Database | Main Router | Legacy |
| `services/brain` | Legacy Intelligence | Neena AI manager state snapshot | Services | Main Router | Legacy |
| `routers/broadcast` | API Router | Broadcast endpoints | Broadcast Service | Frontend | Legacy |

---

# 8. Business Modules (Future / Planned)

| Module Name | Layer | Purpose | Dependencies | Consumers | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `modules/radio` | Business Module | Radio station scheduling & stream automation | Capability Layer | Platform Users | Future |
| `modules/crm` | Business Module | Customer relationship & lead pipeline | Capability Layer | Platform Users | Future |

# Business Operating System (B.O.S.) — Project History

---

# Phase 1

### Product
AI Radio Manager

### Purpose
Radio automation, playout management, voice broadcasts, and listener interaction.

### Outcome
- Working AI Radio Station Manager product with Neena as the default manager profile.
- Operational live voice streaming, station clock scheduling, and WhatsApp gateway integrations.
- Key foundations established: Safety Kernel, Memory Organization System (MOS), tool loop, and Command Center UI (`admin.orairadio.in`).

### Key Milestones & Lessons
- **One Brain Architecture**: Consolidated multi-agent complexity into a single entry pipeline (`brain.process_message`), preventing dual-brain state desynchronization.
- **Truth Gate & Anti-Lie Enforcement**: Enforced strict factual verification (Owner Run Kernel / Truth Gate) so that AI never claims non-executed actions or non-existent tools.
- **System Hardening & TLS**: Established `admin.orairadio.in` reverse proxy architecture, LE cert automation, and isolated process limits for station stability.
- **Lesson Learned**: Relying on NLU string/keyword matching or regex for intent detection introduces brittleness and hard-to-maintain patch loops.

---

# Phase 2

### Product
Business Manager

### Purpose
Expand platform capabilities beyond radio into broader business operations and multi-actor management.

### Problems
- **Business Logic in Core**: Business-specific and industry-specific logic gradually entered the Core Runtime.
- **Complex Workflows**: Responsibilities became mixed between execution logic, tool catalogs, and external services.
- **Repeated Patch Fixes**: Patch fixes introduced architectural coupling across layers.
- **Increased Architectural Coupling**: Direct dependencies developed between runtime execution and specific service implementations.

### Lessons Learned
- Software features must not dictate core runtime architecture.
- Industry-specific business logic must remain completely separate from the core operational runtime.

---

# Phase 3

### Product
Business Operating System (B.O.S.)

### Decision
Project restarted as Business Operating System (B.O.S.). Neena AI Radio Manager serves as the default manager profile and initial migration source.

### Reasons
- Need universal architecture capable of operating any business across any industry.
- Need modular runtime with strict lifecycle execution.
- Need replaceable providers (LLM models, databases, messaging channels).
- Need configurable AI manager profiles (Neena, Maya, Alex, etc.).
- Need reusable business capabilities (`Messaging`, `Scheduling`, `Memory`, `Tasks`, `Workflows`).

---

# Sprint-6 Kernel Governance Milestone

### Milestone
Knowledge Consolidation & Kernel Governance (Sprint-6 Completed)

### Accomplishments
- **Kernel Integration Review**: Evaluated end-to-end cognitive runtime flow (`Intent → AI Orchestrator → Reasoning Engine → Goal Manager → Decision Engine → Policy Engine → Planner → Plan Executor → Capability Registry → Adapter Router`) in [`KERNEL_REVIEW.md`](file:///c:/Projects/b.o.s/KERNEL_REVIEW.md).
- **Graph Orchestrator**: Established [`GraphOrchestrator`](file:///c:/Projects/b.o.s/backend/core/graph/graph_orchestrator.py) under `backend/core/graph/` to coordinate independent graph context (`BusinessContextGraph`, `KnowledgeGraph`, `CapabilityGraph`, `WorkflowGraph`, `WorkflowMemory`, `ExecutionContext`).
- **Legacy Knowledge Extraction**: Inspected legacy modules and cataloged all product ideas, workflow ideas, and automation concepts in [`LEGACY_IDEA_CATALOG.md`](file:///c:/Projects/b.o.s/docs/legacy/LEGACY_IDEA_CATALOG.md).
- **Architecture Validator**: Implemented automated layer compliance and dependency checking in [`architecture_validator.py`](file:///c:/Projects/b.o.s/backend/core/architecture_validator.py) generating [`ARCHITECTURE_REPORT.md`](file:///c:/Projects/b.o.s/ARCHITECTURE_REPORT.md) (Architecture Score: 95/100).
- **Module Registry**: Created canonical source of truth for all system modules and layers in [`MODULE_REGISTRY.md`](file:///c:/Projects/b.o.s/MODULE_REGISTRY.md).

---

# Sprint-7 Module Framework Milestone

### Milestone
Module Framework & Extension Architecture (Sprint-7 Completed)

### Accomplishments
- **Base Module Contract**: Implemented [`BaseModule`](file:///c:/Projects/b.o.s/backend/modules/base/module.py), `ModuleMetadata`, `ModuleState`, `ModuleContext`, and `ModuleLifecycle` in `backend/modules/base/`.
- **Module Manifest Parser**: Implemented [`ModuleManifest`](file:///c:/Projects/b.o.s/backend/modules/base/manifest.py) supporting `module.json` and `module.yaml` parsing and pre-load validation.
- **Runtime Module Registry & Loader**: Implemented [`RuntimeModuleRegistry`](file:///c:/Projects/b.o.s/backend/modules/registry.py) and [`ModuleLoader`](file:///c:/Projects/b.o.s/backend/modules/loader.py) for dynamic instantiation, dependency resolution, and lifecycle state management.
- **Module Sandbox Isolation**: Established [`ModuleSandbox`](file:///c:/Projects/b.o.s/backend/modules/sandbox.py) restricting module modifications to public capability/policy contracts.
- **Module Lifecycle Events**: Integrated [`ModuleEventPublisher`](file:///c:/Projects/b.o.s/backend/modules/events.py) emitting `ModuleInstalled`, `ModuleLoaded`, `ModuleEnabled`, `ModuleDisabled`, and `ModuleRemoved` on `RuntimeEventBus`.
- **Reference Module**: Built [`NotesModule`](file:///c:/Projects/b.o.s/backend/modules/reference/notes_module/notes_module.py) registering `notes` capability, `notes_workflow`, and `create_note` command.
- **ADR Documented**: Created [`ADR-001`](file:///c:/Projects/b.o.s/docs/adr/ADR-001-Module-Extension-Architecture.md) defining the module extension architecture.

---

# Sprint-8 Service Resolution & Dependency Injection Milestone

### Milestone
Service Resolution & Dependency Injection (Sprint-8 Completed)

### Accomplishments
- **Service Contract**: Implemented [`BaseService`](file:///c:/Projects/b.o.s/backend/core/services/base_service.py), `ServiceMetadata`, `ServiceContext`, `ServiceScope`, and `ServiceLifecycle` in `backend/core/services/`.
- **Runtime Service Registry**: Implemented [`RuntimeServiceRegistry`](file:///c:/Projects/b.o.s/backend/core/services/registry.py) supporting registration, resolution, replacement, unregistration, and factory scopes without hardcoded services.
- **Dependency Injection Container**: Built [`ServiceContainer`](file:///c:/Projects/b.o.s/backend/core/services/container.py) supporting constructor injection, lazy resolution, dependency graph traversal, and circular dependency detection (`CircularDependencyError`).
- **Service Discovery Facade**: Implemented [`ServiceDiscovery`](file:///c:/Projects/b.o.s/backend/core/services/discovery.py) as the single public resolution entry point for Modules, Runtime, Graphs, Capabilities, and Adapters.
- **Service Lifecycle Events**: Integrated [`ServiceEventPublisher`](file:///c:/Projects/b.o.s/backend/core/services/events.py) publishing `ServiceRegistered`, `ServiceResolved`, `ServiceStarted`, `ServiceStopped`, and `ServiceReplaced` to `RuntimeEventBus`.
- **Service Health & Diagnostics**: Implemented [`ServiceHealth`](file:///c:/Projects/b.o.s/backend/core/services/health.py) for readiness and liveness diagnostic reporting.
- **Reference Service**: Built [`ClockService`](file:///c:/Projects/b.o.s/backend/core/services/reference/clock_service.py) proving service resolution, DI, health checks, and replacement.
- **ADR Documented**: Created [`ADR-002`](file:///c:/Projects/b.o.s/docs/adr/ADR-002-Service-Layer-Dependency-Injection.md) defining the Service Layer and Dependency Injection.

---

# Sprint-9 Execution Pipeline & Command Bus Milestone

### Milestone
Execution Pipeline & Command Bus (Sprint-9 Completed)

### Accomplishments
- **Command Contract**: Implemented [`Command`](file:///c:/Projects/b.o.s/backend/core/execution/command.py), `CommandMetadata`, `CommandContext`, `CommandResult`, and `ExecutionState` in `backend/core/execution/`.
- **Command Bus**: Implemented [`CommandBus`](file:///c:/Projects/b.o.s/backend/core/execution/command_bus.py) providing central dispatching, queueing, execution, status tracking, and cancellation.
- **6-Stage Execution Pipeline**: Built [`ExecutionPipeline`](file:///c:/Projects/b.o.s/backend/core/execution/pipeline.py) enforcing `Validate → Authorize → Prepare → Execute → Verify → Finalize`.
- **Middleware Chain**: Implemented [`MiddlewareChain`](file:///c:/Projects/b.o.s/backend/core/execution/middleware.py) supporting stacked middleware hooks for Logging, Metrics, Tracing, and Policy.
- **Transaction Context**: Implemented [`ExecutionTransaction`](file:///c:/Projects/b.o.s/backend/core/execution/transaction.py) managing `correlation_id` and nested execution contexts.
- **Execution Events**: Integrated [`ExecutionEventPublisher`](file:///c:/Projects/b.o.s/backend/core/execution/events.py) emitting `ExecutionStarted`, `ExecutionCompleted`, `ExecutionFailed`, and `ExecutionCancelled` to `RuntimeEventBus`.
- **Reference Command**: Built [`EchoCommand`](file:///c:/Projects/b.o.s/backend/core/execution/reference/echo_command.py) validating pipeline execution.
- **ADR Documented**: Created [`ADR-003`](file:///c:/Projects/b.o.s/docs/adr/ADR-003-Execution-Pipeline-Command-Bus.md) defining the Execution Pipeline & Command Bus architecture.

---

# Sprint-9.5 Core Freeze Closure Milestone

### Milestone
Core Freeze Closure & Future Extension Registry (Sprint-9.5 Completed)

### Accomplishments
- **Core Freeze Declaration**: Officially locked B.O.S. Core v1.0 in [`CORE_FREEZE.md`](file:///c:/Projects/b.o.s/CORE_FREEZE.md) establishing clear allowed and forbidden change policies.
- **Future Extension Registry**: Documented postponed architectural concepts (Durable Workflows, Execution Persistence, Memory v2 Vector Store, Multi-Tenant Scoping, Saga Compensation, Workflow Resume) in [`docs/CORE_FUTURE_EXTENSIONS.md`](file:///c:/Projects/b.o.s/docs/CORE_FUTURE_EXTENSIONS.md).
- **ADR Documented**: Created [`ADR-004`](file:///c:/Projects/b.o.s/docs/adr/ADR-004-Core-Freeze-v1.md) ratifying permanent B.O.S. Core v1.0 architectural freeze.

---

# Sprint-10 Provider Framework Milestone

### Milestone
Provider Framework Architecture (Sprint-10 Completed)

### Accomplishments
- **Base Provider Contract**: Implemented [`BaseProvider`](file:///c:/Projects/b.o.s/backend/providers/base/base_provider.py), `ProviderMetadata`, `ProviderContext`, `ProviderState`, `ProviderLifecycle`, and `ProviderScope` in `backend/providers/base/`.
- **Provider Manifest Parser**: Implemented [`ProviderManifest`](file:///c:/Projects/b.o.s/backend/providers/base/manifest.py) supporting `provider.json` and `provider.yaml` parsing.
- **Runtime Provider Registry**: Implemented [`RuntimeProviderRegistry`](file:///c:/Projects/b.o.s/backend/providers/registry.py) supporting registration, priority sorting, capability indexing, enabling/disabling, replacement, and unregistration.
- **Provider Loader & Resolver**: Implemented [`ProviderLoader`](file:///c:/Projects/b.o.s/backend/providers/loader.py) and [`ProviderResolver`](file:///c:/Projects/b.o.s/backend/providers/resolver.py) for dynamic capability-based provider resolution based on priority and health.
- **Provider Health & Diagnostics**: Implemented [`ProviderHealth`](file:///c:/Projects/b.o.s/backend/providers/health.py) for liveness, readiness, degraded, and diagnostic reporting.
- **Provider Events**: Integrated [`ProviderEventPublisher`](file:///c:/Projects/b.o.s/backend/providers/events.py) publishing `ProviderRegistered`, `ProviderLoaded`, `ProviderEnabled`, `ProviderDisabled`, `ProviderHealthChanged`, and `ProviderRemoved` to `RuntimeEventBus`.
- **Reference Providers**: Built [`LocalEchoProvider`](file:///c:/Projects/b.o.s/backend/providers/reference/local_echo_provider.py) (priority 10) and [`MemoryEchoProvider`](file:///c:/Projects/b.o.s/backend/providers/reference/memory_echo_provider.py) (priority 20).
- **ADR Documented**: Created [`ADR-005`](file:///c:/Projects/b.o.s/docs/adr/ADR-005-Provider-Framework-Architecture.md) defining the Provider Framework architecture.

---

# Sprint-11 Configuration & Secrets Framework Milestone

### Milestone
Configuration, Secrets & Environment Framework (Sprint-11 Completed)

### Accomplishments
- **Base Configuration Contract**: Implemented [`BaseConfiguration`](file:///c:/Projects/b.o.s/backend/config/base/base_configuration.py), `ConfigurationMetadata`, `ConfigurationContext`, `ConfigurationScope`, and `ConfigurationSource` in `backend/config/base/`.
- **Runtime Configuration Registry**: Implemented [`RuntimeConfigurationRegistry`](file:///c:/Projects/b.o.s/backend/config/registry.py) supporting configuration registration, scope keying, and value overrides.
- **Configuration Loader**: Implemented [`ConfigurationLoader`](file:///c:/Projects/b.o.s/backend/config/loader.py) parsing `.env`, OS environment variables, JSON, and YAML into normalized configuration objects.
- **Secrets Framework**: Implemented [`SecretManager`](file:///c:/Projects/b.o.s/backend/config/secrets/secret_manager.py), [`SecretResolver`](file:///c:/Projects/b.o.s/backend/config/secrets/secret_resolver.py), and [`SecretReference`](file:///c:/Projects/b.o.s/backend/config/secrets/secret_reference.py) guaranteeing secret value masking in logs (`***REDACTED***`) and runtime injection into providers.
- **Feature Flag Manager**: Implemented [`FeatureFlagManager`](file:///c:/Projects/b.o.s/backend/config/flags.py) supporting global, tenant-specific, and module-specific feature rollouts.
- **6-Tier Configuration Resolver**: Implemented [`ConfigurationResolver`](file:///c:/Projects/b.o.s/backend/config/resolver.py) enforcing `Runtime → Tenant → Module → Provider → Global → Default` precedence.
- **Reference Provider Configs**: Built [`GeminiProviderConfig`](file:///c:/Projects/b.o.s/backend/config/reference/provider_configs.py), [`OpenAIProviderConfig`](file:///c:/Projects/b.o.s/backend/config/reference/provider_configs.py), and [`WhatsAppProviderConfig`](file:///c:/Projects/b.o.s/backend/config/reference/provider_configs.py).
- **ADR Documented**: Created [`ADR-006`](file:///c:/Projects/b.o.s/docs/adr/ADR-006-Configuration-Framework.md) defining the Configuration & Secrets Framework architecture.

---

# Sprint-13 Platform Activation & Launch Readiness Milestone (2026-10-04)

### Milestone
B.O.S. became a runnable, launchable product: AI-native Runtime, owner dashboard, integrations and deployment.

### Significant Bug Found
- The frozen Runtime could not execute at all. Stages imported the retired `services.brain.*` /
  `services.agent.*` packages, and stage contracts no longer matched each other. `BOSRuntimeEngine`
  also re-ran Plan/Policy/Execute inside later nodes, so one request could execute a side-effecting
  step up to five times. Messaging adapters returned `success=True` without sending anything, and
  the Adapter Router silently fell back to WhatsApp for unknown channels.

### Accomplishments
- **AI-native Runtime (ADR-008)**: Context now runs before Understand. Understanding uses the
  `generate_text` capability with structured output, with no keyword matching. Each plan step is
  evaluated against its capability's declared risk and the owner's Autopilot mode. Every stage runs
  once. Only safe steps are retried. Replies are re-grounded on verified results.
- **Providers**: Claude (default `claude-opus-5-5`, server-side refusal fallback) and Gemini
  `text_generation` providers; SQL conversation memory in its own database; workspace records,
  context, channel messaging and webhook event providers.
- **Workspace business DB** (`backend/workspace/`): profile, contacts, tasks, approvals, activity,
  encrypted connections, API keys, webhook subscriptions, Autopilot runs. Kept separate from memory.
- **Runtime Gateway** (`backend/gateway/`): the single entrance for dashboard, channels, API, MCP
  and Autopilot. It turns pending steps into approvals and verified steps into activity and events.
- **Autopilot** (`backend/autopilot/`): scheduled proactive business reviews through the Runtime.
- **Real channels**: Telegram Bot API, WhatsApp Cloud API, SMTP email. They fail honestly when not connected.
- **HTTP API** (`backend/api/`): owner setup and auth, dashboard API, public `/v1` API with scoped
  keys, Stripe-style signed webhooks, Telegram/WhatsApp inbound webhooks, MCP server at `/mcp`.
- **Dashboard** (`frontend/`): React + TypeScript app with guided onboarding, Today briefing,
  Assistant (owner and customer preview), Inbox, Approvals, Customers, Autopilot, Integrations and
  Settings. Light, dark and mobile layouts.
- **Deployment**: multi-stage `Dockerfile`, `docker-compose.yml` (optional PostgreSQL profile),
  new `.env.example`, GitHub Actions CI. Legacy Neena deploy files moved to `legacy/deploy/`.
- **Tests**: 18 end-to-end tests added (62 total passing).

### Lessons Learned
- A frozen core is only valuable if it runs. Freeze declarations need an executable smoke test.
- "Success" from an integration must come from the external system, never from the adapter itself.

---

# Major Architecture Decisions

- **Runtime owns execution**: AI reasoning generates plans; Runtime validates, authorizes, executes, and verifies every action.
- **Capabilities describe actions**: Platform actions are defined generically without provider-specific code.
- **Adapters integrate providers**: Adapters translate capabilities into external system integrations.
- **Providers are replaceable**: AI models and data storage providers remain plug-and-play.
- **Business Modules contain industry logic**: Radio, CRM, Restaurant, Hospital, and Retail logic belong in isolated modules.
- **AI Manager is configurable**: Identity, tone, voice, and language are profile settings over a single operating system.
- **BOS Core remains generic**: No business-specific or industry-specific logic is permitted inside the BOS Core.
- **Graph Orchestration**: Runtime queries graph context exclusively via `GraphOrchestrator`; graphs remain independent.
- **Installable Modules**: Business verticals plug into the platform via `BaseModule` contracts without kernel modification.
- **Generic Service Layer & DI**: All components discover and resolve services via `ServiceDiscovery` and `ServiceContainer`.
- **Command Bus & Pipeline**: Capabilities and modules execute through `CommandBus` and 6-stage `ExecutionPipeline`.
- **Core v1.0 Freeze**: B.O.S. Core Kernel, Runtime Lifecycle, Graph Layer, Service Layer, and Execution Pipeline are permanently frozen.
- **Provider Framework**: Infrastructure providers plug into `backend/providers/` without modifying the frozen Core.
- **Centralized Configuration & Secrets**: All `.env`, secret credentials, feature flags, and tenant overrides resolve via `ConfigurationResolver` and `SecretManager`.
- **Capability Framework**: Formal `BaseCapability`, `RuntimeCapabilityRegistry`, `CapabilityResolver`, `CapabilityPolicyManager`, `CapabilityEventPublisher` and 3 reference capabilities implemented. Legacy capabilities preserved alongside new framework via compatibility bridge.
- **Legacy Service Classification**: Complete `docs/LEGACY_SERVICE_CLASSIFICATION.md` created — 100+ files in `backend/services/` classified into Generic Platform Capability / Business Module Logic / AI Manager Logic / Infrastructure Provider / Dead Legacy with migration sprint targets.
- **Capability Framework Stabilization**: Removed 100% of `importlib` dynamic imports in the entire `backend/` codebase. Renamed legacy `base.py` to `legacy_base.py` to eliminate module collision with new `base/` package. Compatibility with Frozen Core maintained via standard re-export in `capabilities.base`.
- **B.O.S. Architecture Convergence Audit**: Evaluated entire codebase structure, classifying 100% of files (reported in `docs/REPOSITORY_CONVERGENCE_REPORT.md`). Verified architecture compliance with automated validation tool (Architectural Score: 95/100, report in `ARCHITECTURE_REPORT.md`). Obsolete modules in `MODULE_REGISTRY.md` marked as RETIRED.
- **Legacy Capability Elimination**: Removed all legacy capability files (`messaging.py`, `scheduling.py`, `memory.py`, `automation.py`) containing business-specific and radio-specific actions from the platform capability package. Archived all business logic code to `legacy/business_extract/`. Reduced `legacy_base.py` to the bare minimum compatibility registry required by the Frozen Core. B.O.S. Capability Framework is now 100% generic, pure, and ready for business module plug-ins in Sprint-13.
- **AI-Native Runtime Activation (ADR-008)**: Context precedes Understanding; intent is understood by AI through capabilities; policy is per step using capability-declared risk (`read | safe | external | sensitive`) and the owner's Autopilot mode; all interfaces enter through the Runtime Gateway.
- **Trust Boundaries Hardened (PR #1 security reviews)**: API key scopes become Runtime grants (including action-level grants such as `tasks.create_task`). Keys always act as staff, and their conversations and caller-asserted contact identities live in the key's own namespace. Customer self-service steps may set only declared fields. Autopilot reads customer-written text, so unattended it only reads records and adds tasks; other changes wait for the owner. Channel webhooks are signed and size-capped.


---

# Current Direction

The existing project will **not** be rewritten from scratch. It will be migrated through controlled architectural refactoring.

### Migration Order

KEEP
↓
REFACTOR
↓
EXTRACT
↓
REPLACE
↓
RETIRE

Nothing is removed or deleted until its replacement is verified.

---

# Completed Task Log (Sprint-0 to Sprint-13)

Moved here from `project_status.md` on 2026-10-06 so the status file holds only the current state.

- Foundation completed (`docs/foundation.md`)
- Architecture specification completed (`docs/System Architecture Specification v0.1.md`)
- Runtime specification completed (`docs/Runtime Specification v0.1.md`)
- Engineering specification completed (`docs/runtime.md`)
- Roadmap completed (`docs/roadmap.md`)
- Migration Matrix completed (`docs/Migration Blueprint v0.1.md`)
- Product Specification completed (`docs/PRODUCT SPECIFICATION (BPS).md`)
- Architecture Audit completed
- Runtime Separation (`backend/runtime/` package with 11-stage B.O.S. Runtime lifecycle)
- Workflow-Driven State Graph Runtime Architecture (`RuntimeState`, `WorkflowGraph`, `WorkflowNode`, `WorkflowEdge`, `GraphPlanner`, `BOSRuntimeEngine` state machine)
- TASK-003: Universal Capability Registry (`backend/runtime/registry/` and `UniversalCapabilityRegistry`)
- TASK-004: Workflow Template System (`backend/runtime/workflow/templates/` with `approval`, `notification`, `task`, `meeting`, `customer_request`)
- TASK-005: Event Bus (`backend/runtime/events/` with `RuntimeEventBus`, `RuntimeEvent`, `EventType`, `EventSubscription`)
- TASK-006: Execution Context (`backend/runtime/context/` with `ExecutionContext`)
- TASK-007: Intent Engine (`backend/runtime/intent/` with `IntentEngine`, `IntentObject`, `IntentClassifier`)
- TASK-008: Decision Engine (`backend/runtime/decision/` with `DecisionEngine`, `DecisionResult`, `DecisionRules`)
- TASK-009: Policy Engine v2 (`backend/runtime/policy/` with `PolicyEngineV2`, `SecurityPolicy`, `ApprovalPolicy`, `PermissionsPolicy`, `BusinessPolicy`, `ExecutionPolicy`)
- TASK-010: Workflow Memory (`backend/runtime/workflow_memory/` with `WorkflowMemory`, `WorkflowStore`, `PatternStore`, `HistoryStore`, `WorkflowIndex`)
- TASK-011: Business Context Graph (`backend/runtime/business_graph/` & `backend/core/graph/business/`)
- TASK-012: Universal Entity Model (`backend/runtime/entities/` with `UniversalEntity`, `EntityType`)
- TASK-012.5: Capability Graph (`backend/core/graph/capability/` with `CapabilityGraph`, `CapabilityNode`, `CapabilityEdge`, `CapabilityResolver`)
- TASK-013: Knowledge Graph (`backend/runtime/knowledge_graph/` & `backend/core/graph/knowledge/`)
- TASK-014: Graph Query Engine (`backend/runtime/graph_query/` with `GraphQueryEngine`, `GraphQuery`, `QueryFilter`, `GraphResolver`)
- TASK-015: Base Adapter Architecture (`backend/adapters/` with `BaseAdapter`, `AdapterRequest`, `AdapterResponse`, `AdapterStatus`, `AdapterRegistry`)
- TASK-016: Messaging Adapters (`backend/adapters/messaging/` with `WhatsAppAdapter`, `TelegramAdapter`, `EmailAdapter`)
- TASK-017: System & Integration Adapters (`backend/adapters/system/` with `CalendarAdapter`, `VoiceAdapter`, `PaymentsAdapter`, `StorageAdapter`)
- TASK-018: Adapter Router & Capability Integration (`backend/adapters/router.py` with `AdapterRouter`)
- TASK-019: AI Orchestrator (`backend/runtime/orchestrator/` with `AIOrchestrator`, `OrchestratorState`, `OrchestratorContext`, `RoutingStrategy`)
- TASK-020: Reasoning Engine (`backend/runtime/reasoning/` with `ReasoningEngine`, `ReasoningResult`, `BusinessReasoner`, `KnowledgeReasoner`, `MemoryReasoner`, `CapabilityReasoner`)
- TASK-021: Goal Manager (`backend/runtime/goals/` with `GoalManager`, `Goal`, `GoalState`, `GoalBreakdownEngine`, `GoalProgressTracker`)
- TASK-022: Plan Executor (`backend/runtime/plan_executor/` with `PlanExecutor`, `ExecutorState`, `ExecutorStatus`, `PlanCheckpoint`, `RollbackHandler`, `StepRunner`)
- TASK-023: Kernel Integration Review ([`KERNEL_REVIEW.md`](file:///c:/Projects/b.o.s/KERNEL_REVIEW.md))
- TASK-024: Graph Orchestrator ([`GraphOrchestrator`](file:///c:/Projects/b.o.s/backend/core/graph/graph_orchestrator.py))
- TASK-025: Legacy Knowledge Extraction ([`LEGACY_IDEA_CATALOG.md`](file:///c:/Projects/b.o.s/docs/legacy/LEGACY_IDEA_CATALOG.md))
- TASK-026: Architecture Validator ([`architecture_validator.py`](file:///c:/Projects/b.o.s/backend/core/architecture_validator.py) & [`ARCHITECTURE_REPORT.md`](file:///c:/Projects/b.o.s/ARCHITECTURE_REPORT.md))
- TASK-027: Module Registry ([`MODULE_REGISTRY.md`](file:///c:/Projects/b.o.s/MODULE_REGISTRY.md))
- TASK-028: Base Module Contract (`backend/modules/base/` with `BaseModule`, `ModuleMetadata`, `ModuleState`, `ModuleContext`, `ModuleLifecycle`)
- TASK-029: Module Manifest Parser (`backend/modules/base/manifest.py` with `ModuleManifest`)
- TASK-030: Runtime Module Registry (`backend/modules/registry.py` with `RuntimeModuleRegistry`)
- TASK-031: Module Loader (`backend/modules/loader.py` with `ModuleLoader`)
- TASK-032: Module Sandbox (`backend/modules/sandbox.py` with `ModuleSandbox`)
- TASK-033: Module Lifecycle Events (`backend/modules/events.py` with `ModuleEventPublisher`)
- TASK-034: Reference Notes Module (`backend/modules/reference/notes_module/` with `NotesModule`)
- TASK-035: Base Service Contract (`backend/core/services/` with `BaseService`, `ServiceMetadata`, `ServiceContext`, `ServiceScope`, `ServiceLifecycle`)
- TASK-036: Runtime Service Registry (`backend/core/services/registry.py` with `RuntimeServiceRegistry`)
- TASK-037: Dependency Injection Container (`backend/core/services/container.py` with `ServiceContainer`, `CircularDependencyError`)
- TASK-038: Service Discovery (`backend/core/services/discovery.py` with `ServiceDiscovery`)
- TASK-039: Service Lifecycle Events (`backend/core/services/events.py` with `ServiceEventPublisher`)
- TASK-040: Service Health & Diagnostics (`backend/core/services/health.py` with `ServiceHealth`, `HealthState`)
- TASK-041: Reference Clock Service (`backend/core/services/reference/clock_service.py` with `ClockService`)
- TASK-042: Base Command Contract (`backend/core/execution/` with `Command`, `CommandMetadata`, `CommandContext`, `CommandResult`, `ExecutionState`)
- TASK-043: Command Bus (`backend/core/execution/command_bus.py` with `CommandBus`)
- TASK-044: 6-Stage Execution Pipeline (`backend/core/execution/pipeline.py` with `ExecutionPipeline`)
- TASK-045: Middleware Chain (`backend/core/execution/middleware.py` with `MiddlewareChain`, `LoggingMiddleware`)
- TASK-046: Transaction Context (`backend/core/execution/transaction.py` with `ExecutionTransaction`)
- TASK-047: Execution Lifecycle Events (`backend/core/execution/events.py` with `ExecutionEventPublisher`)
- TASK-048: Reference Echo Command (`backend/core/execution/reference/echo_command.py` with `EchoCommand`)
- TASK-050: Base Provider Contract (`backend/providers/base/` with `BaseProvider`, `ProviderMetadata`, `ProviderContext`, `ProviderState`, `ProviderLifecycle`, `ProviderScope`)
- TASK-051: Provider Manifest Parser (`backend/providers/base/manifest.py` with `ProviderManifest`)
- TASK-052: Runtime Provider Registry (`backend/providers/registry.py` with `RuntimeProviderRegistry`)
- TASK-053: Provider Loader (`backend/providers/loader.py` with `ProviderLoader`)
- TASK-054: Dynamic Provider Resolver (`backend/providers/resolver.py` with `ProviderResolver`)
- TASK-055: Provider Health & Diagnostics (`backend/providers/health.py` with `ProviderHealth`, `ProviderHealthStatus`)
- TASK-056: Provider Event Publisher (`backend/providers/events.py` with `ProviderEventPublisher`)
- TASK-057: Reference Providers (`backend/providers/reference/` with `LocalEchoProvider`, `MemoryEchoProvider`)
- TASK-059: Base Configuration Contract (`backend/config/base/` with `BaseConfiguration`, `ConfigurationMetadata`, `ConfigurationContext`, `ConfigurationScope`, `ConfigurationSource`)
- TASK-060: Runtime Configuration Registry (`backend/config/registry.py` with `RuntimeConfigurationRegistry`)
- TASK-061: Configuration Loader (`backend/config/loader.py` with `ConfigurationLoader`)
- TASK-062: Secrets Framework (`backend/config/secrets/` with `SecretManager`, `SecretResolver`, `SecretReference`)
- TASK-063: Feature Flag Manager (`backend/config/flags.py` with `FeatureFlagManager`)
- TASK-064: 6-Tier Configuration Resolver (`backend/config/resolver.py` with `ConfigurationResolver`)
- TASK-065: Reference Configurations (`backend/config/reference/` with `GeminiProviderConfig`, `OpenAIProviderConfig`, `WhatsAppProviderConfig`)
- TASK-066: Legacy Service Classification Report (`docs/LEGACY_SERVICE_CLASSIFICATION.md` — official migration map for all `backend/services/` files, 100+ files classified)
- TASK-067: Base Capability Contract (`backend/capabilities/base/` with `BaseCapability`, `CapabilityMetadata`, `CapabilityContext`, `CapabilityResult`, `CapabilityScope`, `CapabilityLifecycle`)
- TASK-068: Capability Manifest Parser (`backend/capabilities/base/manifest.py` with `CapabilityManifest`)
- TASK-069: Runtime Capability Registry (`backend/capabilities/registry.py` with `RuntimeCapabilityRegistry`, category index, version index, dependency validation)
- TASK-070: Capability Resolver (`backend/capabilities/resolver.py` with `CapabilityResolver` — 4-step pipeline: resolve → validate action → validate policies → execute)
- TASK-071: Capability Policy Manager (`backend/capabilities/policies.py` with `CapabilityPolicyManager` — allowed/denied providers, permissions, tenant restrictions, feature flags)
- TASK-072: Capability Event Publisher (`backend/capabilities/events.py` with `CapabilityEventPublisher`, 5 event types, graceful EventBus degradation)
- TASK-073: Reference Capabilities (`backend/capabilities/reference/` with `GenerateTextCapability`, `StoreDocumentCapability`, `SendMessageCapability`)
- TASK-074: Capability Framework Tests (41 tests passing — TASK-067 to TASK-073 fully covered)
- TASK-075: Capability Framework Stabilization (`backend/capabilities/legacy_base.py`, 0 `importlib` usages in `backend/`, `docs/SPRINT_12_1_STABILIZATION_REPORT.md`)
- TASK-076: B.O.S. Architecture Convergence Audit (`docs/REPOSITORY_CONVERGENCE_REPORT.md`, `ARCHITECTURE_REPORT.md`, updated legacy service registry to RETIRED)
- TASK-077: Legacy Capability Elimination (`backend/capabilities/legacy_base.py` minimum compatibility bridge, legacy files archived to `legacy/business_extract/`)
- TASK-078: Runtime activation (ADR-008): context before understanding, AI understanding via `generate_text`, per-step policy on declared risk + Autopilot mode, run-once engine, safe-only retry, grounded responses
- TASK-079: AI providers: `ClaudeProvider`, `GeminiProvider` (`backend/providers/ai/`), keys from dashboard vault or env
- TASK-080: Workspace business DB (`backend/workspace/`) and SQL conversation memory provider (separate store)
- TASK-081: Core capabilities (`backend/capabilities/core/`): contacts, tasks, integration_events, business_context, conversation_memory
- TASK-082: Runtime Gateway (`backend/gateway/`) and Autopilot proactive reviews + scheduler (`backend/autopilot/`)
- TASK-083: Real channel adapters: Telegram, WhatsApp Cloud API, SMTP email; no silent fallback in `AdapterRouter`
- TASK-084: HTTP API (`backend/api/`): owner setup/auth, dashboard API, public `/v1`, signed webhooks, channel webhooks, MCP server
- TASK-085: Owner dashboard (`frontend/`): onboarding, Today, Assistant, Inbox, Approvals, Customers, Autopilot, Integrations, Settings
- TASK-086: Deployment: multi-stage `Dockerfile`, `docker-compose.yml`, `.env.example`, CI workflow, `README.md`
- TASK-087: End-to-end platform tests (`backend/tests/test_platform_api.py`)

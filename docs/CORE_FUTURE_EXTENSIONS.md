# B.O.S. Core Future Extensions Registry

## Overview
This document registers architectural reservations for future platform capabilities intentionally postponed beyond **Core v1.0 Freeze**. 

Postponing these extensions prevents premature optimization and keeps the Core Kernel clean, generic, and unburdened by enterprise infrastructure complexities until Provider & Business Module validation occurs.

---

# 1. Durable Workflow Execution

| Field | Details |
| :--- | :--- |
| **Purpose** | Guarantees long-running workflow state persistence across server restarts, node crashes, and network partitions. |
| **Reason Postponed** | Core v1.0 focuses on state graph correctness and in-memory execution contracts. Adding distributed event loop persistence before Provider validation creates unnecessary coupling. |
| **Future Design Direction** | Implement an abstract `DurableEventLoop` and `StatePersistenceEngine` backing the `WorkflowGraph` state machine. |
| **Target Phase** | B.O.S. Enterprise / Distributed Runtime (Phase 9) |
| **Dependencies** | Provider Layer (Storage / Redis Provider) |

---

# 2. Execution Persistence

| Field | Details |
| :--- | :--- |
| **Purpose** | Persistent checkpointing, pause/resume state serialization, and crash recovery for `PlanExecutor`. |
| **Reason Postponed** | In-memory `PlanCheckpoint` and `RollbackHandler` satisfy single-node execution requirements. External database storage belongs in Provider Layer adapters. |
| **Future Design Direction** | Extend `PlanCheckpoint` to serialize execution snapshots to PostgreSQL / Redis via `StorageProvider`. |
| **Target Phase** | Provider Layer Implementation (Sprint-10) |
| **Dependencies** | Service Layer (`StorageService`), Provider Contracts |

---

# 3. Memory Architecture v2 & Vector Provider Interface

| Field | Details |
| :--- | :--- |
| **Purpose** | Multi-tiered memory engine combining Working Memory, Conversation Memory, Business Memory, Episodic Memory, and Semantic Memory via vector embeddings. |
| **Reason Postponed** | Core v1.0 establishes `WorkflowMemory`, `PatternStore`, and `HistoryStore`. Semantic RAG vector stores require replaceable AI Embeddings & Vector DB providers. |
| **Future Design Direction** | Introduce `VectorStoreProvider` interface (`similarity_search`, `upsert_embeddings`) integrated into `KnowledgeGraph` and `MemoryEngine`. |
| **Target Phase** | Sprint-10 (RAG & Memory Intelligence Upgrade) |
| **Dependencies** | Provider Layer (Gemini/OpenAI Embeddings & Vector DB Provider) |

---

# 4. Multi-Tenant Context & Isolation

| Field | Details |
| :--- | :--- |
| **Purpose** | Explicit `tenant_id` propagation, data segregation, tenant-scoped rate limits, and permission boundaries for multi-organization SaaS hosting. |
| **Reason Postponed** | Single-tenant and local deployment workloads take precedence during Core v1.0 migration. Adding tenant scoping early complicates single-tenant runtime execution. |
| **Future Design Direction** | Enforce `tenant_id` in `CommandContext`, `ExecutionContext`, `NormalizedRequest`, and database persistence models. |
| **Target Phase** | Enterprise SaaS / Multi-Tenant Release (Phase 9) |
| **Dependencies** | Multi-tenant Identity & Authorization Policies |

---

# 5. Saga / Compensation Protocol

| Field | Details |
| :--- | :--- |
| **Purpose** | Distributed two-phase commit and compensation action execution across external adapters (e.g. issuing a payment refund if downstream booking fails). |
| **Reason Postponed** | Single-step `RollbackHandler` in `PlanExecutor` handles single-node step failure. Distributed Sagas require multi-adapter transaction coordination. |
| **Future Design Direction** | Define `CompensationCommand` contract executed by `CommandBus` when a multi-adapter transaction fails midway. |
| **Target Phase** | Advanced Integration & Capabilities |
| **Dependencies** | Command Bus (`ExecutionTransaction`), Adapter Layer |

---

# 6. Workflow Resume & External Approval Hooks

| Field | Details |
| :--- | :--- |
| **Purpose** | Asynchronous execution pausing for out-of-band human approvals (e.g. email/web links) with event-driven resume hooks. |
| **Reason Postponed** | Synchronous and inline approval checks (`WAITING_APPROVAL`) in `PlanExecutor` cover active manager sessions. Out-of-band webhooks require external API endpoints. |
| **Future Design Direction** | Add `ApprovalToken` generator and webhook listener resuming `PlanExecutor.resume_execution` via `RuntimeEventBus`. |
| **Target Phase** | Business Module Integrations |
| **Dependencies** | Event Bus (`APPROVAL_GRANTED`), Command Bus |

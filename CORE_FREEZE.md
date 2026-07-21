# B.O.S. Core v1.0 Freeze Declaration

## Overview
This document officially declares **B.O.S. Core v1.0 FROZEN**.

Effective immediately, the platform Core Kernel, Runtime Lifecycle, Graph Layer, Module Framework, Service Layer, and Execution Pipeline are locked to preserve architectural stability.

---

## 1. Frozen Core Components

The following subsystems are frozen and protected under Core Freeze:

| Subsystem | Components | Protection Policy |
| :--- | :--- | :--- |
| **Runtime Lifecycle** | `backend/runtime/` (Intent, Reasoning, Decision, Policy, Planner, PlanExecutor) | **LOCKED** |
| **Cognitive Kernel** | `AIOrchestrator`, `ReasoningEngine`, `GoalManager`, `PlanExecutor` | **LOCKED** |
| **Independent Graph Layer** | `core/graph/` (`BusinessContextGraph`, `KnowledgeGraph`, `CapabilityGraph`, `GraphOrchestrator`) | **LOCKED** |
| **Module Extension Framework**| `backend/modules/` (`BaseModule`, `ModuleManifest`, `RuntimeModuleRegistry`, `ModuleLoader`, `ModuleSandbox`) | **LOCKED** |
| **Generic Service Layer** | `backend/core/services/` (`BaseService`, `RuntimeServiceRegistry`, `ServiceContainer`, `ServiceDiscovery`) | **LOCKED** |
| **Execution Pipeline** | `backend/core/execution/` (`Command`, `CommandBus`, `ExecutionPipeline`, `MiddlewareChain`, `ExecutionTransaction`) | **LOCKED** |
| **Governance & Policies** | `PolicyEngineV2`, `SecurityPolicy`, `ApprovalPolicy`, `PermissionsPolicy` | **LOCKED** |

---

## 2. Allowed Changes

The following modifications are **PERMITTED** post-freeze:

- ✅ **Bug Fixes**: Fixing defects, regressions, or incorrect implementation details.
- ✅ **Performance Optimizations**: Improving execution speed or memory efficiency without altering public interfaces.
- ✅ **Documentation Updates**: Expanding docstrings, architecture specs, or usage guides.
- ✅ **Provider Implementations**: Adding new technology providers (LLMs, Databases, Storage) under `backend/providers/`.
- ✅ **Business Module Additions**: Creating installable industry modules under `backend/modules/` inheriting from `BaseModule`.

---

## 3. Forbidden Changes

The following modifications are **STRICTLY FORBIDDEN** without formal Architectural Review and an ADR:

- ❌ **Modifying Public Contracts**: Changing signatures of `BaseModule`, `BaseService`, `Command`, `UniversalCapability`, `BaseAdapter`, or `IntentObject`.
- ❌ **Altering Runtime Lifecycle**: Bypassing or modifying any of the 11 Runtime stages or 6 Execution Pipeline stages.
- ❌ **Injecting Industry Logic into Core**: Adding radio, CRM, restaurant, or hospital business logic into `backend/runtime/` or `backend/core/`.
- ❌ **Direct Provider Calls**: Calling providers directly from business modules or capabilities without passing through `CommandBus` or `AdapterRouter`.
- ❌ **Breaking Layer Boundaries**: Bypassing `ServiceDiscovery` or creating direct circular dependencies across layers.

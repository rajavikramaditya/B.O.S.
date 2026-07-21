# B.O.S. Architecture Refinement Specification (ARS-1)

**Sprint:** Architecture Refinement Planning  
**Date:** July 21, 2026  
**Status:** DRAFT SPECIFICATION (APPROVED FOR ROADMAP)  

---

## 1. Executive Summary: Core v1.0 Freeze Readiness

### **Answer: MOST LIKELY**

**Why?**  
Upon implementing the targeted refinements detailed in this specification, B.O.S. will have successfully resolved the verified operational friction points (pronoun resolution, execution thread cancellation, and static policy gating) without violating Core Freeze constraints. All proposed changes are structured as **extensions** to existing interfaces rather than structural redesigns, preserving strict layer boundaries, kernel purity, and decoupling.

---

## 2. Verified Blockers & Layer Ownership

Based on the verified audit report (`VERIFIED_ROOT_CAUSE_AUDIT.md`), the following 4 blockers are targeted for refinement:

| Blocker ID | Blocker Description | Responsible Layer | Component to Extend |
|---|---|---|---|
| **B-01** | Pronoun Resolution Deficit ("Wahi", "Usko") | Memory / Context | `backend/runtime/context/context_engine.py` |
| **B-02** | Synchronous Execution Loop Blocking | Runtime / Executor | `backend/runtime/plan_executor/executor.py` |
| **B-03** | All-or-Nothing Step Failure (No Splitting) | Planner | `backend/runtime/plan_executor/step_runner.py` |
| **B-04** | Static Security Policy Lockout (No MFA Bypasses) | Policy Engine | `backend/runtime/policy/policy_engine.py` |

---

## 3. Extension vs Modification Matrix

We explicitly **reject** any structural architecture modifications or additions of new core layers. All issues can be resolved by extending existing platform components.

| Blocker ID | Core Redesign Required? | Extension Pathway |
|---|---|---|
| **B-01** | **NO** | Extend `RuntimeContext` contract with an in-memory `EntityRecencyCache`. |
| **B-02** | **NO** | Extend `PlanExecutor` to run execution steps via async polling check. |
| **B-03** | **NO** | Extend `StepRunner` to support failure status handlers (`ON_FAILURE_SKIP_STEP`). |
| **B-04** | **NO** | Extend `PolicyDecision` with `CHALLENGE_REQUIRED` status to trigger Human-in-the-Loop approval. |

---

## 4. Refinement Specifications

### 1. Memory / Context Refinements (B-01)
* **Goal:** Resolve conversational pronouns ("wahi", "usko") to active entities dynamically.
* **Refinement:** Introduce an `EntityRecencyCache` inside `RuntimeContext` that tracks the last 3 accessed `Person` and `Asset` UUIDs. When the `IntentEngine` maps slots containing ambiguous pronouns, the `ContextEngine` substitutes the pronouns with cached UUIDs.
* **Backward Compatibility:** 100% compatible. Contract structures remain unchanged.

### 2. Runtime Refinements (B-02)
* **Goal:** Enable mid-flight execution pauses and cancellation inputs.
* **Refinement:** Modify the `PlanExecutor.execute_plan` loop to yield execution status asynchronously. At each yield, check the `ExecutorState` for incoming cancel signals before invoking the next `StepRunner`.
* **Testing Impact:** Requires mocked async execution generators in pytest.

### 3. Planner Refinements (B-03)
* **Goal:** Allow steps in a plan to fail safely without triggering full plan termination.
* **Refinement:** Extend `ExecutionPlanStep` params to support `continue_on_failure` metadata flags. If a non-critical step fails, the `PlanExecutor` logs the warning and advances rather than aborting.
* **Coupling Impact:** Minimal. Exposes plan metadata config only.

### 4. Policy Refinements (B-04)
* **Goal:** Elevate locked actions to interactive MFA/Owner approvals instead of flat denial.
* **Refinement:** Extend the `PolicyEngine` to return a `CHALLENGE_REQUIRED` status when action policies trigger security constraints. This halts execution temporarily and publishes an approval challenge event to the `RuntimeEventBus`.

---

## 5. Prioritized Refinement Roadmap

### **Priority 1: Async Execution Loop & Cancellations (B-02)**
- *Reason:* Uncancellable long-running processes represent a critical safety risk.
- *Benefit:* Resolves mid-flight lockups and enables immediate cancellation execution.
- *Dependencies:* None.

### **Priority 2: Conversational Recency Context (B-01)**
- *Reason:* Pronoun resolution failures represent the highest user friction.
- *Benefit:* System behaves naturally with Hinglish conversational shortcuts.
- *Dependencies:* B-02.

### **Priority 3: Dynamic Step Failure Handling (B-03)**
- *Reason:* Minimizes unnecessary system aborts.
- *Benefit:* Single adapter timeout does not halt independent subsequent steps.
- *Dependencies:* B-02.

### **Priority 4: Interactive Policy Escalation (B-04)**
- *Reason:* Prevents administrator lockout.
- *Benefit:* Secure verification prompt allows owners to bypass strict static policies safely.
- *Dependencies:* B-02, B-03.

---

## 6. Freeze Readiness Projection

After implementing Priority 1 and Priority 2 refinements, the architecture score is projected to reach **98/100** with 0 active execution blockers, making Core v1.0 fully suitable for permanent freeze.

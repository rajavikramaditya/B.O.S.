# ADR-008: AI-Native Runtime Activation

## Context
The 11-stage Runtime (Core v1.0, frozen) could not execute: stages imported the
retired `services.brain.*` / `services.agent.*` packages, stage contracts no longer
matched each other, and `BOSRuntimeEngine` re-ran Planning, Policy and Execution in
every later node — so a single request could execute a side-effecting step up to
five times. Intent understanding relied on keyword matching, which violates the
Natural Language Rule in `AGENTS.md`.

## Problem
1. Understanding a message with AI needs conversation memory and business context,
   but the frozen order ran **Understand before Context**.
2. Approval was all-or-nothing and tied to radio-specific action names.
3. Nothing grounded the final reply on what actually happened.

## Decision
1. **Stage order** — Context (stage 2) now runs before Understand (stage 3).
   All 11 stages remain; only these two swap. `GraphPlanner` edges reflect it.
2. **Understanding by AI** — `UnderstandingEngine` calls the `generate_text`
   capability with a structured-output schema (intent, goal, entities, proposed
   steps, reply, insights). The Runtime never calls a provider directly
   (`runtime/cognition.py` is the single doorway).
3. **Declared risk** — every plannable capability declares per-action risk
   (`read | safe | external | sensitive`) and parameters in
   `CapabilityMetadata.configuration`. Policy evaluates each step independently:
   allowed / pending (human approval) / denied, using the risk, the actor role and
   the owner's Autopilot mode (`off | assist | autopilot | autonomous`).
   `ApprovalPolicy.requires_human()` is the single rule.
4. **Run once** — the engine carries stage outputs in a per-request run record;
   every node executes once. RETRY re-runs only failed `read`/`safe` steps;
   `external`/`sensitive` steps are never retried automatically.
5. **Grounded response** — when steps ran, Response re-grounds the draft reply on
   verified results (completed / waiting / failed) before it is sent.
6. **Explicit plans** — integrations may submit a plan; it still passes Policy,
   Execution, Verification and Memory. Only the owner's approval path may mark a
   plan `preapproved`.

## Consequences
- The Runtime is runnable and industry-neutral; business behaviour comes from the
  business profile, capabilities and modules.
- Contract dataclasses gained optional fields only (backward compatible).
- `ContextEngine`'s B-01 keyword recency cache is kept (KEEP) but no longer on the
  main path; it is a RETIRE candidate once nothing references it.
- `IntentClassifier` (keyword based) is no longer used by the lifecycle; RETIRE candidate.

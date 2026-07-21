# AGENTS.md
# Business Operating System (B.O.S.)

---

# Mission

Build B.O.S. as a universal Business Operating System.

Do not optimize for quick fixes.

Optimize for architecture, maintainability and long-term scalability.

---

# Current Project Status

Product : Business Operating System (B.O.S.)

Current Stage : Architecture Migration

Current Sprint : Sprint-0 (Architecture Refactoring)

Current Goal : Transform Neena AI Radio Manager into a generic Business Operating System.

Current Default AI Manager : Neena

Important:
Neena is only the default AI profile.
The product is B.O.S.

---

# Project History

The project started as an AI Radio Station Manager.

As features increased, business logic gradually entered the Core Runtime.

Responsibilities became mixed.

Several patch fixes introduced architectural coupling.

The project has now restarted as Business Operating System (B.O.S.).

From this point onward, architecture has higher priority than implementation speed.

---

# Architecture

Every request must follow this lifecycle.

Business

↓

Runtime

↓

Policy

↓

Capability

↓

Adapter

↓

Provider

↓

Verification

↓

Memory

↓

Response

Never bypass Runtime.

---

# Core Principles

- Single Responsibility Principle (SRP).
- Loose Coupling using APIs, JSON and Contracts.
- High Cohesion.
- Directory by Feature.
- Runtime owns execution.
- Capabilities describe actions.
- Adapters integrate external systems.
- Providers remain replaceable.
- Business Modules contain industry-specific logic.

---

# Directory Philosophy

Organize code by feature.

Correct

modules/

runtime/

capabilities/

adapters/

providers/

frontend/

backend/

Incorrect

helpers/

misc/

common/

utils2/

---

# Natural Language Rule

Business understanding MUST NOT depend on:

- regex
- keyword matching
- string comparison
- hardcoded intents

Allowed exceptions

- Authentication
- Button IDs
- Health endpoints
- Protocol parsing
- Infrastructure routing

Everything else must be interpreted by the Runtime using AI reasoning.

---

# Forbidden Changes

Never:

- Put business logic inside Runtime.
- Put provider logic inside Capabilities.
- Call providers directly from business modules.
- Hardcode company-specific logic.
- Duplicate existing logic.
- Create helper dumping files.
- Skip policy validation.
- Skip execution verification.
- Mix Memory with Business Database.

---

# Before Writing Code

Always ask:

1. Is this Runtime?
2. Is this a Capability?
3. Is this an Adapter?
4. Is this a Provider?
5. Is this a Business Module?

If uncertain, stop and redesign.

---

# Migration Rules

Never delete first.

Migration order:

KEEP

↓

REFACTOR

↓

EXTRACT

↓

REPLACE

↓

RETIRE

Nothing is removed until its replacement is verified.

---

# Documentation Rules

Every completed task MUST update:

- PROJECT_STATUS.md
- PROJECT_HISTORY.md

Update these only if changes are meaningful.

Update architecture documents only when architecture actually changes.

Never leave documentation inconsistent with implementation.

---

# PROJECT_STATUS.md Rules

Maintain only the current state.

Include:

- Current Sprint
- Current Milestone
- Current Priority
- Completed Tasks
- In Progress
- Blockers
- Next Task

Do not include historical information.

---

# PROJECT_HISTORY.md Rules

Record only major events.

Examples:

- Architecture decisions
- Breaking changes
- Major migrations
- Lessons learned
- Significant bugs
- Production incidents

Never delete history.

Append new entries chronologically.

---

# Code Quality

Prefer:

- Small files
- Clear names
- Composition
- Interfaces
- Contracts
- Tests

Avoid:

- Global state
- Circular imports
- Hidden dependencies
- Magic values
- Temporary hacks

---

# Definition of Done

A task is complete only when:

✓ Feature works.

✓ Architecture remains correct.

✓ No duplicated logic.

✓ Tests pass.

✓ Documentation updated.

✓ PROJECT_STATUS.md updated.

✓ PROJECT_HISTORY.md updated (if required).

---

# Final Rule

Business Operating System is a platform, not a chatbot.

Every implementation must make the platform more generic, more modular and easier to extend.

If a shortcut weakens the architecture, do not implement it.

---

# Operational Safety & Guardrails (Anti-Mistake)

1. **Do not lie to the owner.** Never claim ran / verified / live status unless checked this turn.
2. **Safety Kernel & Permissions:** Do not bypass Safety Kernel or remove owner confirm on protected / irreversible actions.
3. **No Secrets:** Never print `.env` values or expose secrets in chat, commits, logs, or replies.
4. **Deploy Protection:** No deploy / VM / `.env` / DB schema / mobile (`orai-radio-station/**`) / Redis·Postgres·Azura restart without **explicit owner approval this turn**.
5. **Communication Style:** Always use simple, natural Hinglish (aam bhasha) in chat/communication. Keep responses concise, friendly, and easy to understand.

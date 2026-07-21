# B.O.S. MIGRATION MATRIX

## Migration Blueprint v0.1

---

# Document Information

| Field       | Value                                                             |
| ----------- | ----------------------------------------------------------------- |
| Document ID | BOS-MIG-001                                                       |
| Version     | 0.1                                                               |
| Status      | Draft                                                             |
| Depends On  | FOUNDATION, ARCHITECTURE, RUNTIME, ENGINEERING, ROADMAP           |
| Purpose     | Convert the existing Neena project into Business Operating System |

---

# 1. Purpose

This document is the bridge between the **current implementation** and the **target B.O.S. architecture**.

Unlike architecture documents, this document contains implementation decisions.

Every existing folder, service and component will eventually appear in this document.

This document becomes the migration guide for both humans and AI coding agents.

---

# 2. Migration Philosophy

The project will **NOT** be rewritten.

The project will evolve.

Migration follows four actions only.

| Action   | Meaning                                                  |
| -------- | -------------------------------------------------------- |
| KEEP     | Component already matches BOS direction                  |
| REFACTOR | Improve internal architecture                            |
| EXTRACT  | Move to a different layer without changing functionality |
| RETIRE   | Remove after replacement                                 |

Nothing is deleted until its replacement is verified.

---

# 3. Current Project Identity

Current Product

```
Neena AI Radio Manager
```

Target Product

```
Business Operating System
```

Current Default Business

```
Radio Station
```

Target

```
Generic Business Platform
```

Current AI

```
Neena
```

Target

```
Configurable AI Manager Profile
```

---

# 4. Migration Strategy

Migration happens from the outside inward.

Order:

```
Business Modules

↓

Adapters

↓

Capabilities

↓

Runtime

↓

Core
```

The Core is modified last.

---

# 5. Folder Migration Matrix

| Current                      | Future            | Action   |
| ---------------------------- | ----------------- | -------- |
| backend/main.py              | runtime/bootstrap | Refactor |
| backend/database.py          | persistence layer | Refactor |
| routers/broadcast.py         | modules/radio     | Extract  |
| routers/azuracast_webhook.py | modules/radio     | Extract  |
| services/tools               | capability layer  | Split    |
| services/brain               | runtime           | Refactor |
| frontend                     | generic dashboard | Rewrite  |
| config                       | keep              | Improve  |
| tests                        | keep              | Expand   |
| deploy                       | keep              | Improve  |

---

# 6. Runtime Migration

Current

```
Router

↓

Service

↓

Database
```

Target

```
Router

↓

Runtime

↓

Policy

↓

Planner

↓

Capability

↓

Adapter

↓

Provider
```

The Runtime becomes the only execution coordinator.

---

# 7. AI Migration

Current

```
Neena
```

Future

```
AI Manager Profile
```

Every customer may define

* Name
* Voice
* Personality
* Language
* Avatar
* Tone

No implementation should depend on the manager name.

---

# 8. Radio Migration

Current Situation

Radio functionality exists inside the main platform.

Target

```
modules/

radio/

crm/

restaurant/

hospital/

retail/
```

Radio becomes the first Business Module.

No Runtime modification should be required.

---

# 9. Tool Migration

Current

Business tools and platform tools are mixed.

Future

```
Capability

↓

Tool

↓

Adapter
```

Examples

Messaging

↓

WhatsApp Tool

↓

WhatsApp Adapter

The business never calls adapters directly.

---

# 10. Memory Migration

Current

Conversation and business information are closely coupled.

Future

Three logical systems.

Working Memory

Long-term Memory

Business Data

Knowledge remains independent.

---

# 11. Database Migration

Current

Single business database.

Future

Logical separation.

Business Data

Knowledge

Memory

Audit

These may share one physical database but remain independent models.

---

# 12. Dashboard Migration

Current

Radio-oriented dashboard.

Target

Generic Business Dashboard.

Widgets become installable.

Examples

CRM Widget

Sales Widget

Orders Widget

Employees Widget

Tasks Widget

Notifications Widget

Radio Widget

The dashboard becomes modular.

---

# 13. Capability Migration

Current

Capabilities are spread across services.

Future

```
Capabilities/

Messaging

Scheduling

Knowledge

Memory

Workflow

Contacts

Notifications

Content

Search

Automation
```

Capabilities become permanent platform APIs.

---

# 14. Adapter Migration

Current

Platform integrations exist inside services.

Future

```
Adapters/

WhatsApp

Telegram

Email

Voice

Calendar

Payment

Storage

Database
```

Adapters never contain business logic.

---

# 15. Provider Migration

Providers become replaceable.

Examples

AI

Gemini

GPT

Claude

Ollama

Database

SQLite

PostgreSQL

Storage

Local

Cloud

No provider should affect Runtime logic.

---

# 16. Migration Order

Phase 1

Freeze Documentation

Status

✓ Complete

---

Phase 2

Project Audit

Status

✓ Complete (Architecture Level)

---

Phase 3

Folder Migration

Status

Pending

---

Phase 4

Runtime Separation

Status

Pending

---

Phase 5

Capability Layer

Status

Pending

---

Phase 6

Adapter Layer

Status

Pending

---

Phase 7

Business Modules

Status

Pending

---

Phase 8

Generic Dashboard

Status

Pending

---

Phase 9

B.O.S. v1 Release

Status

Future

---

# 17. Definition of Migration Complete

Migration is complete only when:

✓ No business logic exists inside BOS Core.

✓ Runtime coordinates every request.

✓ Capabilities are reusable.

✓ Providers are replaceable.

✓ Radio is a Business Module.

✓ AI Manager is configurable.

✓ Dashboard is business-independent.

✓ New industries require only new modules.

---

# 18. Final Migration Decision

The existing project is **not** technical debt.

It is Version Zero of the Business Operating System.

The goal is not to replace it.

The goal is to evolve it into a universal platform through controlled architectural migration.

This document becomes the implementation blueprint for every future engineering task.

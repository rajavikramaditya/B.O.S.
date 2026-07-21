# ============================================================================
# B.O.S. PROJECT INTELLIGENCE
# Chief Architect Reference
# ============================================================================
#
# PURPOSE
#
# This document is NOT part of the product.
#
# It is the working memory of the Chief Architect (ChatGPT).
#
# Before giving implementation instructions to any coding agent,
# consult this document first.
#
# Never guess.
#
# Always know where the source of truth exists.
#
# ============================================================================

# 1. FOUNDATION.md

Purpose

Defines WHY B.O.S. exists.

Contains

• Vision
• Mission
• Philosophy
• Product Identity
• Core Principles
• Product Scope

Consult when

- creating new architecture
- changing product direction
- validating whether a feature belongs in BOS

Never modify architecture without checking FOUNDATION.

------------------------------------------------------------------------------

# 2. ARCHITECTURE.md

Purpose

Defines WHAT the system is.

Contains

• Layered Architecture
• Component Boundaries
• Responsibilities
• Dependency Direction
• Replaceability
• Module Isolation

Consult when

- creating new Runtime components
- creating Graphs
- creating Adapters
- creating Providers
- reviewing dependencies

Architecture always overrides implementation.

------------------------------------------------------------------------------

# 3. RUNTIME.md

Purpose

Defines HOW Runtime works.

Contains

Execution lifecycle

Observation

↓

Understanding

↓

Intent

↓

Reasoning

↓

Decision

↓

Planning

↓

Policy

↓

Execution

↓

Verification

↓

Memory

↓

Response

Consult when

- modifying Runtime
- changing execution flow
- creating new Runtime engines

Never bypass Runtime lifecycle.

------------------------------------------------------------------------------

# 4. ENGINEERING.md

Purpose

Defines coding standards.

Contains

SRP

Loose Coupling

High Cohesion

Testing

Directory Structure

Naming

Documentation

Code Quality

Consult before every implementation.

------------------------------------------------------------------------------

# 5. PRODUCT_SPECIFICATION.md

Purpose

Defines product capabilities.

Contains

Actors

Universal Objects

Universal Capabilities

Business Features

AI Manager

Business Modules

Interaction Model

Consult when

creating new capabilities

Never invent product features.

------------------------------------------------------------------------------

# 6. MIGRATION_MATRIX.md

Purpose

Defines migration strategy.

Contains

KEEP

REFACTOR

EXTRACT

REPLACE

RETIRE

Consult when

working with legacy code.

Never migrate blindly.

------------------------------------------------------------------------------

# 7. PROJECT_STATUS.md

Purpose

Current implementation state.

Contains

Completed Sprint

Current Sprint

Implemented Components

Pending Work

Consult

before every new sprint.

Update

after meaningful implementation.

------------------------------------------------------------------------------

# 8. PROJECT_HISTORY.md

Purpose

Architecture history.

Contains

Major decisions

Completed milestones

Migration history

Update

ONLY when architecture changes.

------------------------------------------------------------------------------

# 9. AGENTS.md

Purpose

Coding agent rules.

Contains

Permanent Rules

Forbidden Actions

Architecture Rules

Development Rules

Quality Rules

Coding Workflow

Always obey.

------------------------------------------------------------------------------

# 10. MODULE_REGISTRY.md

Purpose

Complete module inventory.

Contains

Every Module

Dependencies

Consumers

Status

Stable

Experimental

Deprecated

Consult before creating new modules.

Never duplicate modules.

------------------------------------------------------------------------------

# 11. LEGACY_IDEA_CATALOG.md

Purpose

Knowledge extracted from legacy project.

Contains

Business Ideas

Workflow Ideas

Capability Ideas

AI Behaviour Ideas

UX Ideas

Consult

before inventing new capabilities.

Old ideas may already solve the problem.

------------------------------------------------------------------------------

# 12. ARCHITECTURE_REPORT.md

Purpose

Architecture validation.

Contains

Layer violations

Circular dependencies

Duplicate responsibilities

Kernel issues

Consult

before approving major implementation.

------------------------------------------------------------------------------

# 13. ADR/

Purpose

Architecture Decision Records.

Contains

Decision

Reason

Alternatives

Consequences

Consult

when changing architecture.

Never reverse ADR without new ADR.

------------------------------------------------------------------------------

# DECISION FLOW

Need product vision?

↓

FOUNDATION

------------------------

Need architecture?

↓

ARCHITECTURE

------------------------

Need runtime?

↓

RUNTIME

------------------------

Need coding rules?

↓

ENGINEERING

------------------------

Need capability?

↓

PRODUCT_SPECIFICATION

------------------------

Need migration?

↓

MIGRATION_MATRIX

------------------------

Need current progress?

↓

PROJECT_STATUS

------------------------

Need history?

↓

PROJECT_HISTORY

------------------------

Need agent rules?

↓

AGENTS

------------------------

Need legacy thinking?

↓

LEGACY_IDEA_CATALOG

------------------------

Need architecture validation?

↓

ARCHITECTURE_REPORT

------------------------

Need module lookup?

↓

MODULE_REGISTRY

------------------------

Need architecture decision?

↓

ADR

# ============================================================================
# END
# ============================================================================
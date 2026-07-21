# ADR-001: Installable Module Extension Architecture

## Context
B.O.S. (Business Operating System) requires a completely industry-agnostic core runtime. To support specialized business verticals (such as Radio Broadcasting, CRM, Restaurants, Hospitals, Retail, etc.) without hardcoding industry logic into the Kernel, an installable module extension framework is necessary.

## Decision
We establish the `backend/modules/` framework with strict sandbox isolation:
1. **Base Module Contract**: All business modules inherit from `BaseModule` (`backend/modules/base/module.py`), declaring `ModuleMetadata`, `ModuleState`, `ModuleContext`, and `ModuleLifecycle`.
2. **Module Manifest**: Every module supplies a validated `module.json` or `module.yaml` manifest specifying capabilities, permissions, settings, and dependencies.
3. **Runtime Module Registry & Loader**: Modules are dynamically loaded (`ModuleLoader`), registered (`RuntimeModuleRegistry`), and enabled/disabled without hardcoding module names in the Runtime.
4. **Sandbox Boundary**: Modules may register platform capabilities, workflows, policies, and commands via public contracts (`ModuleSandbox`). Modules MUST NOT modify Runtime state, Graphs, or Core services directly.
5. **Event Bus Integration**: Module lifecycle transitions publish events (`ModuleInstalled`, `ModuleLoaded`, `ModuleEnabled`, `ModuleDisabled`, `ModuleRemoved`) to `RuntimeEventBus`.

## Status
ACCEPTED

## Consequences
- The Kernel remains permanently industry-neutral.
- Third-party or domain-specific logic resides exclusively in installable business modules.
- New business modules require zero modifications to the B.O.S. Core Kernel.

# ADR-003: Execution Pipeline & Command Bus

## Context
In B.O.S. (Business Operating System), capabilities, modules, and providers must not invoke execution directly or bypass governance. Every execution request must pass through a standardized, stage-gated pipeline and command bus.

## Decision
We establish the `backend/core/execution/` framework:
1. **Command Contract**: All executable commands inherit from `Command` (`backend/core/execution/command.py`), declaring `CommandMetadata`, `CommandContext`, `CommandResult`, and `ExecutionState`.
2. **Command Bus**: `CommandBus` (`backend/core/execution/command_bus.py`) provides dispatch, queueing, execution, status tracking, and cancellation capabilities.
3. **Execution Pipeline**: `ExecutionPipeline` (`backend/core/execution/pipeline.py`) enforces a strict 6-stage lifecycle: `Validate → Authorize → Prepare → Execute → Verify → Finalize`.
4. **Execution Middleware**: `MiddlewareChain` (`backend/core/execution/middleware.py`) supports stacked middleware hooks for Logging, Metrics, Tracing, and Policy checks.
5. **Transaction Context**: `ExecutionTransaction` (`backend/core/execution/transaction.py`) maintains `correlation_id` and `execution_id` across nested execution calls.
6. **Execution Events**: Lifecycle transitions trigger `ExecutionStarted`, `ExecutionCompleted`, `ExecutionFailed`, and `ExecutionCancelled` events on `RuntimeEventBus`.
7. **Reference Command**: `EchoCommand` (`backend/core/execution/reference/echo_command.py`) validates end-to-end pipeline execution without business logic.

## Status
ACCEPTED

## Consequences
- Capabilities and modules no longer call external systems or providers directly; all execution flows through `CommandBus`.
- The Provider Layer (Sprint-10) can plug into this pipeline cleanly with full transaction tracing and stage-gated policy authorization.

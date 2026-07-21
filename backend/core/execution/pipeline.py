"""B.O.S. Execution Pipeline v0.1

Strict 6-stage execution pipeline:
Validate -> Authorize -> Prepare -> Execute -> Verify -> Finalize
Every command passes every stage.
"""

from typing import Any, Dict
from .command import Command
from .command_context import CommandContext
from .command_result import CommandResult
from .execution_state import ExecutionState
from .middleware import MiddlewareChain
from .events import ExecutionEventPublisher, ExecutionEventType
from runtime.policy import PolicyEngineV2


class ExecutionPipeline:
    """Orchestrates the 6-stage command execution pipeline wrapped in middleware."""

    def __init__(self, middleware_chain: MiddlewareChain | None = None):
        self.middleware_chain = middleware_chain or MiddlewareChain()

    def run(self, command: Command, context: CommandContext) -> CommandResult:
        return self.middleware_chain.execute_chain(command, context, self._core_pipeline)

    def _core_pipeline(self, command: Command, context: CommandContext) -> CommandResult:
        cmd_name = command.metadata.name
        ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_STARTED, cmd_name, context.to_dict())

        # Stage 1: Validate
        if not command.validate(context):
            res = CommandResult(
                success=False,
                state=ExecutionState.FAILED,
                error_message=f"Command validation failed for '{cmd_name}'",
            )
            ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_FAILED, cmd_name, res.to_dict())
            return res

        # Stage 2: Authorize
        policy_decision = PolicyEngineV2.evaluate_request(
            role=context.role,
            action=cmd_name,
            params=context.params,
        )
        if policy_decision.status == "DENY":
            res = CommandResult(
                success=False,
                state=ExecutionState.FAILED,
                error_message=f"Authorization denied for action '{cmd_name}': {policy_decision.reason}",
            )
            ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_FAILED, cmd_name, res.to_dict())
            return res

        # Stage 3: Prepare
        prepared_params = dict(context.params)
        prepared_params["_prepared"] = True
        context.params = prepared_params

        # Stage 4: Execute
        try:
            result = command.execute(context)
        except Exception as ex:
            res = CommandResult(
                success=False,
                state=ExecutionState.FAILED,
                error_message=f"Command execution error in '{cmd_name}': {str(ex)}",
            )
            ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_FAILED, cmd_name, res.to_dict())
            return res

        # Stage 5: Verify
        if not result.success:
            result.state = ExecutionState.FAILED
            ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_FAILED, cmd_name, result.to_dict())
            return result

        # Stage 6: Finalize
        result.state = ExecutionState.COMPLETED
        ExecutionEventPublisher.publish(ExecutionEventType.EXECUTION_COMPLETED, cmd_name, result.to_dict())
        return result

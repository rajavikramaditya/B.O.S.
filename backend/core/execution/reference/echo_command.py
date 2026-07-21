"""B.O.S. Reference Echo Command v0.1

Minimal reference command validating the execution pipeline. Zero business logic.
"""

from typing import Any, Dict
from ..command import Command
from ..command_metadata import CommandMetadata
from ..command_context import CommandContext
from ..command_result import CommandResult
from ..execution_state import ExecutionState


class EchoCommand(Command):
    """Reference command echoing input payload through the pipeline."""

    def __init__(self, name: str = "echo"):
        meta = CommandMetadata(
            name=name,
            description="Reference command validating the execution pipeline.",
        )
        super().__init__(meta)

    def validate(self, context: CommandContext) -> bool:
        return True

    def execute(self, context: CommandContext) -> CommandResult:
        message = context.params.get("message", "echo_default")
        return CommandResult(
            success=True,
            state=ExecutionState.COMPLETED,
            data={"echoed_message": message, "received_params": context.params},
        )

"""B.O.S. Command Bus v0.1

Central entry point dispatching, queueing, executing, and tracking commands.
Capabilities and Modules dispatch commands via CommandBus.
"""

from typing import Any, Dict, List, Optional
from .command import Command
from .command_context import CommandContext
from .command_result import CommandResult
from .execution_state import ExecutionState
from .pipeline import ExecutionPipeline
from .transaction import ExecutionTransaction


class CommandBus:
    """Central Command Bus orchestrating dispatch and execution pipeline."""

    _commands: Dict[str, Command] = {}
    _pipeline = ExecutionPipeline()
    _active_transactions: Dict[str, ExecutionTransaction] = {}

    @classmethod
    def register_command(cls, command: Command) -> None:
        cls._commands[command.metadata.name.lower()] = command

    @classmethod
    def dispatch(
        cls,
        command_name: str,
        params: Dict[str, Any] | None = None,
        role: str = "customer",
        actor_id: str = "system",
        transaction: Optional[ExecutionTransaction] = None,
    ) -> CommandResult:
        cmd = cls._commands.get(command_name.lower())
        if not cmd:
            return CommandResult(
                success=False,
                state=ExecutionState.FAILED,
                error_message=f"Command '{command_name}' is not registered on CommandBus.",
            )

        tx = transaction or ExecutionTransaction()
        cls._active_transactions[tx.execution_id] = tx

        context = CommandContext(
            command_id=f"cmd_{tx.execution_id[:8]}",
            actor_id=actor_id,
            role=role,
            params=params or {},
            transaction_id=tx.execution_id,
        )

        return cls._pipeline.run(cmd, context)

    @classmethod
    def get_command(cls, name: str) -> Optional[Command]:
        return cls._commands.get(name.lower())

    @classmethod
    def clear(cls) -> None:
        cls._commands.clear()
        cls._active_transactions.clear()

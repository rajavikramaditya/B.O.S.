"""B.O.S. Abstract Command v0.1

Abstract Base Class for all commands executed via the CommandBus & ExecutionPipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from .command_metadata import CommandMetadata
from .command_context import CommandContext
from .command_result import CommandResult


class Command(ABC):
    """Abstract base class for platform commands."""

    def __init__(self, metadata: CommandMetadata):
        self.metadata = metadata

    @abstractmethod
    def validate(self, context: CommandContext) -> bool:
        """Validate input parameters in context before execution."""
        pass

    @abstractmethod
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute command logic and return CommandResult."""
        pass

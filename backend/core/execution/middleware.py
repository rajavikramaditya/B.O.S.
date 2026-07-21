"""B.O.S. Execution Middleware Chain v0.1

Provides extensible middleware hooks for Logging, Metrics, Tracing, and Policy checks.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from .command import Command
from .command_context import CommandContext
from .command_result import CommandResult


class BaseMiddleware(ABC):
    """Abstract base middleware for the Execution Pipeline."""

    @abstractmethod
    def process(
        self, command: Command, context: CommandContext, next_stage: Callable[[Command, CommandContext], CommandResult]
    ) -> CommandResult:
        pass


class LoggingMiddleware(BaseMiddleware):
    def process(
        self, command: Command, context: CommandContext, next_stage: Callable[[Command, CommandContext], CommandResult]
    ) -> CommandResult:
        start = time.time()
        res = next_stage(command, context)
        elapsed = (time.time() - start) * 1000.0
        res.execution_time_ms = round(elapsed, 2)
        return res


class MiddlewareChain:
    """Chain executor managing stacked pipeline middlewares."""

    def __init__(self, middlewares: List[BaseMiddleware] | None = None):
        self.middlewares = middlewares or [LoggingMiddleware()]

    def execute_chain(
        self, command: Command, context: CommandContext, core_executor: Callable[[Command, CommandContext], CommandResult]
    ) -> CommandResult:
        def build_pipeline(index: int) -> Callable[[Command, CommandContext], CommandResult]:
            if index >= len(self.middlewares):
                return core_executor
            return lambda cmd, ctx: self.middlewares[index].process(cmd, ctx, build_pipeline(index + 1))

        return build_pipeline(0)(command, context)

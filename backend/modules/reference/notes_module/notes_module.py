"""B.O.S. Reference Notes Module v0.1

Minimal reference module proving extension architecture.
Registers 1 capability ('notes'), 1 workflow ('notes_workflow'), and 1 command ('create_note').
Zero industry-specific business logic.
"""

from typing import Any, Dict
from modules.base import BaseModule, ModuleContext, ModuleLifecycle


class NotesModule(BaseModule):
    """Reference implementation of an installable B.O.S. module."""

    def initialize(self, context: ModuleContext) -> bool:
        self.context = context

        # 1. Register command
        self.commands = {"create_note": self.create_note_command}

        # 2. Register workflow
        self.workflows = {"notes_workflow": ["create_note", "verify_note"]}

        self.state.status = ModuleLifecycle.LOADED
        return True

    def enable(self) -> bool:
        self.state.active = True
        self.state.status = ModuleLifecycle.ENABLED
        return True

    def disable(self) -> bool:
        self.state.active = False
        self.state.status = ModuleLifecycle.DISABLED
        return True

    def unload(self) -> bool:
        self.state.status = ModuleLifecycle.UNLOADED
        return True

    def create_note_command(self, title: str, content: str) -> Dict[str, Any]:
        return {"note_id": "note_101", "title": title, "content": content, "status": "CREATED"}

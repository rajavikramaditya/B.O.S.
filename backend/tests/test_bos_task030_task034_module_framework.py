"""Tests for TASK-030 to TASK-034: Module Framework, Sandbox, Events, and Reference Module."""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from modules import (
    RuntimeModuleRegistry,
    ModuleLoader,
    ModuleSandbox,
    ModuleLifecycle,
)
from modules.reference.notes_module import NotesModule
from runtime.registry import UniversalCapabilityRegistry


def setup_function():
    RuntimeModuleRegistry.clear()


def test_module_loader_and_reference_module():
    manifest_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "modules", "reference", "notes_module", "module.json")
    )
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_dict = json.load(f)

    # 1. Load module via ModuleLoader
    module = ModuleLoader.load_module(NotesModule, manifest_dict)
    assert module.manifest.name == "notes_module"
    assert module.state.status == ModuleLifecycle.LOADED

    # 2. Check capability registration in UniversalCapabilityRegistry
    cap = UniversalCapabilityRegistry.get("notes")
    assert cap is not None
    assert cap.name == "notes"

    # 3. Enable module via RuntimeModuleRegistry
    assert RuntimeModuleRegistry.enable_module("notes_module") is True
    retrieved = RuntimeModuleRegistry.get("notes_module")
    assert retrieved.state.active is True
    assert retrieved.state.status == ModuleLifecycle.ENABLED

    # 4. Test command execution
    res = retrieved.commands["create_note"](title="Meeting Note", content="Review architecture")
    assert res["status"] == "CREATED"
    assert res["title"] == "Meeting Note"

    # 5. Disable and Unload
    assert RuntimeModuleRegistry.disable_module("notes_module") is True
    assert RuntimeModuleRegistry.unload_module("notes_module") is True
    assert RuntimeModuleRegistry.get("notes_module") is None

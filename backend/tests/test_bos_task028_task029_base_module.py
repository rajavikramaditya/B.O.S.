"""Tests for TASK-028 (Base Module Contract) and TASK-029 (Module Manifest)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from modules.base import (
    BaseModule,
    ModuleContext,
    ModuleLifecycle,
    ModuleManifest,
    ModuleMetadata,
    ModuleState,
)


class DummyTestModule(BaseModule):
    def initialize(self, context: ModuleContext) -> bool:
        self.context = context
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


def test_module_manifest_validation():
    manifest_data = {
        "name": "test_module",
        "version": "1.2.0",
        "author": "Tester",
        "capabilities": ["notes"],
        "dependencies": [],
    }
    manifest = ModuleManifest.from_dict(manifest_data)
    assert manifest.name == "test_module"
    assert manifest.version == "1.2.0"
    assert manifest.validate() is True


def test_base_module_lifecycle():
    manifest = ModuleManifest(name="dummy_module", version="1.0.0")
    module = DummyTestModule(manifest)

    assert module.state.status == ModuleLifecycle.UNLOADED
    ctx = ModuleContext(module_id="dummy_module")

    assert module.initialize(ctx) is True
    assert module.state.status == ModuleLifecycle.LOADED

    assert module.enable() is True
    assert module.state.status == ModuleLifecycle.ENABLED

    assert module.disable() is True
    assert module.state.status == ModuleLifecycle.DISABLED

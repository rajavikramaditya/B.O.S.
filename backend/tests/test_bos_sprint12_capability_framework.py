"""Tests for B.O.S. Sprint-12 Capability Framework (TASK-067 → TASK-074)."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from capabilities.base.base_capability import BaseCapability
from capabilities.base.capability_context import CapabilityContext
from capabilities.base.capability_lifecycle import CapabilityLifecycle
from capabilities.base.capability_metadata import CapabilityMetadata
from capabilities.base.capability_result import CapabilityResult
from capabilities.base.capability_scope import CapabilityScope
from capabilities.base.manifest import CapabilityManifest
from capabilities.events import CapabilityEventPublisher, CapabilityEventType
from capabilities.policies import CapabilityPolicyManager
from capabilities.registry import RuntimeCapabilityRegistry
from capabilities.resolver import CapabilityResolver


# ===========================================================================
# Fixtures & Stubs
# ===========================================================================


class EchoCapability(BaseCapability):
    """Minimal stub capability for testing."""

    def __init__(self, name: str = "echo", category: str = "test"):
        super().__init__(
            metadata=CapabilityMetadata(
                name=name,
                version="1.0.0",
                category=category,
                description="Echo test capability.",
                permissions=[],
                scope=CapabilityScope.GLOBAL,
            )
        )

    def supported_actions(self):
        return ["echo", "ping"]

    def execute(self, action: str, params, context: CapabilityContext) -> CapabilityResult:
        return CapabilityResult(
            success=True,
            capability_name=self.name,
            action=action,
            data={"echo": params.get("message", "pong")},
            message="Echo successful.",
            correlation_id=context.correlation_id,
        )


@pytest.fixture(autouse=True)
def clean_registry_and_policy():
    """Reset registry and policy state before each test."""
    RuntimeCapabilityRegistry.clear()
    CapabilityPolicyManager.clear()
    yield
    RuntimeCapabilityRegistry.clear()
    CapabilityPolicyManager.clear()


# ===========================================================================
# TASK-067: Base Capability Contract
# ===========================================================================


def test_base_capability_metadata():
    cap = EchoCapability()
    assert cap.name == "echo"
    assert cap.version == "1.0.0"
    assert cap.category == "test"
    assert cap.lifecycle == CapabilityLifecycle.REGISTERED


def test_base_capability_supported_actions():
    cap = EchoCapability()
    assert "echo" in cap.supported_actions()
    assert "ping" in cap.supported_actions()
    assert cap.supports_action("echo") is True
    assert cap.supports_action("unknown_action") is False


def test_base_capability_execute_safe_success():
    cap = EchoCapability()
    ctx = CapabilityContext(tenant_id="tenant_a", module_id="mod_test")
    result = cap.execute_safe("echo", {"message": "hello"}, ctx)
    assert result.success is True
    assert result.data["echo"] == "hello"
    assert result.correlation_id == ctx.correlation_id
    assert result.execution_time_ms is not None


def test_base_capability_execute_safe_catches_exception():
    class BrokenCapability(BaseCapability):
        def __init__(self):
            super().__init__(CapabilityMetadata(name="broken", category="test"))

        def supported_actions(self):
            return ["crash"]

        def execute(self, action, params, context):
            raise RuntimeError("Simulated crash")

    cap = BrokenCapability()
    ctx = CapabilityContext()
    result = cap.execute_safe("crash", {}, ctx)
    assert result.success is False
    assert "Simulated crash" in result.error


def test_capability_result_failure_factory():
    result = CapabilityResult.failure(
        capability_name="test_cap",
        action="run",
        error="Something went wrong",
        correlation_id="corr_001",
    )
    assert result.success is False
    assert result.error == "Something went wrong"
    assert result.correlation_id == "corr_001"


def test_capability_context_has_flag():
    ctx = CapabilityContext(feature_flags=["feature_x", "feature_y"])
    assert ctx.has_flag("feature_x") is True
    assert ctx.has_flag("feature_z") is False


def test_capability_scope_values():
    assert CapabilityScope.GLOBAL == "GLOBAL"
    assert CapabilityScope.MODULE == "MODULE"
    assert CapabilityScope.TENANT == "TENANT"
    assert CapabilityScope.SYSTEM == "SYSTEM"


def test_capability_lifecycle_values():
    assert CapabilityLifecycle.UNREGISTERED == "UNREGISTERED"
    assert CapabilityLifecycle.ENABLED == "ENABLED"
    assert CapabilityLifecycle.DEPRECATED == "DEPRECATED"


# ===========================================================================
# TASK-068: Capability Manifest
# ===========================================================================


def test_manifest_from_dict():
    data = {
        "name": "generate_text",
        "version": "2.0.0",
        "category": "ai",
        "description": "Text generation",
        "required_providers": ["llm"],
        "permissions": ["ai:generate"],
        "scope": "GLOBAL",
    }
    manifest = CapabilityManifest.from_dict(data)
    assert manifest.name == "generate_text"
    assert manifest.version == "2.0.0"
    assert manifest.category == "ai"
    assert "llm" in manifest.required_providers
    assert "ai:generate" in manifest.permissions


def test_manifest_from_json():
    json_str = '{"name": "messaging", "version": "1.0.0", "category": "comm"}'
    manifest = CapabilityManifest.from_json(json_str)
    assert manifest.name == "messaging"
    assert manifest.version == "1.0.0"


def test_manifest_from_yaml():
    yaml_str = "name: storage\nversion: 1.2.0\ncategory: data\n"
    manifest = CapabilityManifest.from_yaml(yaml_str)
    assert manifest.name == "storage"
    assert manifest.version == "1.2.0"


def test_manifest_missing_name_raises():
    with pytest.raises(ValueError, match="name"):
        CapabilityManifest.from_dict({"version": "1.0.0"})


def test_manifest_to_metadata():
    data = {
        "name": "test_cap",
        "version": "1.0.0",
        "category": "test",
        "required_providers": ["echo_provider"],
        "scope": "MODULE",
    }
    manifest = CapabilityManifest.from_dict(data)
    meta = manifest.to_metadata()
    assert meta.name == "test_cap"
    assert meta.scope == CapabilityScope.MODULE
    assert "echo_provider" in meta.required_providers


# ===========================================================================
# TASK-069: Capability Registry
# ===========================================================================


def test_registry_register_and_get():
    cap = EchoCapability("echo_cap", "test")
    RuntimeCapabilityRegistry.register(cap)
    resolved = RuntimeCapabilityRegistry.get("echo_cap")
    assert resolved is not None
    assert resolved.name == "echo_cap"


def test_registry_case_insensitive():
    cap = EchoCapability("MyCapability", "test")
    RuntimeCapabilityRegistry.register(cap)
    assert RuntimeCapabilityRegistry.get("mycapability") is not None
    assert RuntimeCapabilityRegistry.get("MYCAPABILITY") is not None


def test_registry_category_index():
    RuntimeCapabilityRegistry.register(EchoCapability("cap_a", "messaging"))
    RuntimeCapabilityRegistry.register(EchoCapability("cap_b", "messaging"))
    RuntimeCapabilityRegistry.register(EchoCapability("cap_c", "storage"))
    results = RuntimeCapabilityRegistry.resolve_by_category("messaging")
    assert len(results) == 2


def test_registry_version_index():
    cap = EchoCapability("versioned_cap", "test")
    RuntimeCapabilityRegistry.register(cap)
    versioned = RuntimeCapabilityRegistry.get_version("versioned_cap", "1.0.0")
    assert versioned is not None


def test_registry_enable_disable():
    cap = EchoCapability("toggle_cap", "test")
    RuntimeCapabilityRegistry.register(cap)
    assert RuntimeCapabilityRegistry.is_enabled("toggle_cap")

    RuntimeCapabilityRegistry.disable("toggle_cap")
    assert not RuntimeCapabilityRegistry.is_enabled("toggle_cap")
    assert RuntimeCapabilityRegistry.get("toggle_cap") is None

    RuntimeCapabilityRegistry.enable("toggle_cap")
    assert RuntimeCapabilityRegistry.is_enabled("toggle_cap")


def test_registry_resolve_for_action():
    RuntimeCapabilityRegistry.register(EchoCapability("echo_runner", "test"))
    cap = RuntimeCapabilityRegistry.resolve_for_action("echo")
    assert cap is not None
    assert cap.name == "echo_runner"


def test_registry_dependency_validation_missing():
    class DependentCapability(BaseCapability):
        def __init__(self):
            super().__init__(
                CapabilityMetadata(
                    name="dep_cap",
                    category="test",
                    dependencies=["missing_dep"],
                )
            )

        def supported_actions(self):
            return ["run"]

        def execute(self, action, params, context):
            return CapabilityResult(success=True, capability_name=self.name, action=action)

    cap = DependentCapability()
    missing = RuntimeCapabilityRegistry.validate_dependencies(cap)
    assert "missing_dep" in missing


def test_registry_dependency_validation_satisfied():
    RuntimeCapabilityRegistry.register(EchoCapability("dep_a", "test"))

    class SatisfiedCapability(BaseCapability):
        def __init__(self):
            super().__init__(
                CapabilityMetadata(
                    name="sat_cap",
                    category="test",
                    dependencies=["dep_a"],
                )
            )

        def supported_actions(self):
            return ["run"]

        def execute(self, action, params, context):
            return CapabilityResult(success=True, capability_name=self.name, action=action)

    cap = SatisfiedCapability()
    missing = RuntimeCapabilityRegistry.validate_dependencies(cap)
    assert missing == []


def test_registry_list_all():
    RuntimeCapabilityRegistry.register(EchoCapability("cap_x", "test"))
    RuntimeCapabilityRegistry.register(EchoCapability("cap_y", "test"))
    listed = RuntimeCapabilityRegistry.list_all()
    names = [c["name"] for c in listed]
    assert "cap_x" in names
    assert "cap_y" in names


# ===========================================================================
# TASK-070: Capability Resolver
# ===========================================================================


def test_resolver_executes_capability():
    RuntimeCapabilityRegistry.register(EchoCapability("echo", "test"))
    RuntimeCapabilityRegistry.enable("echo")
    result = CapabilityResolver.execute("echo", "echo", {"message": "hello"})
    assert result.success is True
    assert result.data["echo"] == "hello"


def test_resolver_unknown_capability():
    result = CapabilityResolver.execute("nonexistent", "run", {})
    assert result.success is False
    assert "not found" in result.error


def test_resolver_unsupported_action():
    RuntimeCapabilityRegistry.register(EchoCapability("echo", "test"))
    RuntimeCapabilityRegistry.enable("echo")
    result = CapabilityResolver.execute("echo", "unsupported_action", {})
    assert result.success is False
    assert "not supported" in result.error


def test_resolver_execute_for_action():
    RuntimeCapabilityRegistry.register(EchoCapability("echo", "test"))
    RuntimeCapabilityRegistry.enable("echo")
    result = CapabilityResolver.execute_for_action("ping", {})
    assert result.success is True


def test_resolver_execute_for_action_not_found():
    result = CapabilityResolver.execute_for_action("nonexistent_action", {})
    assert result.success is False
    assert "No enabled capability" in result.error


# ===========================================================================
# TASK-071: Capability Policies
# ===========================================================================


def test_policy_feature_flag_required():
    RuntimeCapabilityRegistry.register(EchoCapability("flagged_cap", "test"))
    RuntimeCapabilityRegistry.enable("flagged_cap")
    CapabilityPolicyManager.set_required_flags("flagged_cap", ["beta_feature"])

    # Without flag — should fail
    ctx_no_flag = CapabilityContext(feature_flags=[])
    result = CapabilityResolver.execute("flagged_cap", "echo", {}, ctx_no_flag)
    assert result.success is False
    assert "beta_feature" in result.error

    # With flag — should pass
    ctx_with_flag = CapabilityContext(feature_flags=["beta_feature"])
    result = CapabilityResolver.execute("flagged_cap", "echo", {}, ctx_with_flag)
    assert result.success is True


def test_policy_tenant_restriction():
    RuntimeCapabilityRegistry.register(EchoCapability("tenant_cap", "test"))
    RuntimeCapabilityRegistry.enable("tenant_cap")
    CapabilityPolicyManager.set_tenant_restrictions("tenant_cap", ["tenant_a"])

    ctx_wrong = CapabilityContext(tenant_id="tenant_b")
    result = CapabilityResolver.execute("tenant_cap", "echo", {}, ctx_wrong)
    assert result.success is False
    assert "tenant_b" in result.error

    ctx_correct = CapabilityContext(tenant_id="tenant_a")
    result = CapabilityResolver.execute("tenant_cap", "echo", {}, ctx_correct)
    assert result.success is True


def test_policy_permission_required():
    RuntimeCapabilityRegistry.register(EchoCapability("perm_cap", "test"))
    RuntimeCapabilityRegistry.enable("perm_cap")
    CapabilityPolicyManager.set_required_permissions("perm_cap", ["cap:execute"])

    ctx_no_perm = CapabilityContext(configuration={"permissions": []})
    result = CapabilityResolver.execute("perm_cap", "echo", {}, ctx_no_perm)
    assert result.success is False
    assert "cap:execute" in result.error

    ctx_with_perm = CapabilityContext(configuration={"permissions": ["cap:execute"]})
    result = CapabilityResolver.execute("perm_cap", "echo", {}, ctx_with_perm)
    assert result.success is True


def test_policy_allowed_providers():
    CapabilityPolicyManager.set_allowed_providers("test_cap", ["provider_a"])
    allowed, reason = CapabilityPolicyManager.validate(
        "test_cap", CapabilityContext(), provider_name="provider_b"
    )
    assert allowed is False
    assert "provider_b" in reason


def test_policy_denied_providers():
    CapabilityPolicyManager.set_denied_providers("test_cap", ["bad_provider"])
    allowed, reason = CapabilityPolicyManager.validate(
        "test_cap", CapabilityContext(), provider_name="bad_provider"
    )
    assert allowed is False
    assert "bad_provider" in reason


def test_policy_summary():
    CapabilityPolicyManager.set_required_flags("my_cap", ["flag_x"])
    CapabilityPolicyManager.set_tenant_restrictions("my_cap", ["tenant_1"])
    summary = CapabilityPolicyManager.get_policy_summary("my_cap")
    assert "flag_x" in summary["required_flags"]
    assert "tenant_1" in summary["tenant_restrictions"]


# ===========================================================================
# TASK-072: Capability Events
# ===========================================================================


def test_event_publish_does_not_raise():
    """Events should gracefully degrade when EventBus is unavailable."""
    # This must not raise even if RuntimeEventBus is not initialized
    CapabilityEventPublisher.publish(
        CapabilityEventType.CAPABILITY_REGISTERED,
        "test_cap",
        {"version": "1.0.0"},
    )


def test_event_type_constants():
    assert CapabilityEventType.CAPABILITY_REGISTERED == "CapabilityRegistered"
    assert CapabilityEventType.CAPABILITY_ENABLED == "CapabilityEnabled"
    assert CapabilityEventType.CAPABILITY_DISABLED == "CapabilityDisabled"
    assert CapabilityEventType.CAPABILITY_RESOLVED == "CapabilityResolved"
    assert CapabilityEventType.CAPABILITY_FAILED == "CapabilityFailed"


# ===========================================================================
# TASK-073: Reference Capabilities — Provider Mapping
# ===========================================================================


def test_reference_capabilities_importable():
    from capabilities.reference.generate_text_capability import GenerateTextCapability
    from capabilities.reference.send_message_capability import SendMessageCapability
    from capabilities.reference.store_document_capability import StoreDocumentCapability

    assert GenerateTextCapability().name == "generate_text"
    assert StoreDocumentCapability().name == "store_document"
    assert SendMessageCapability().name == "send_message"


def test_generate_text_capability_metadata():
    from capabilities.reference.generate_text_capability import GenerateTextCapability

    cap = GenerateTextCapability()
    assert cap.category == "ai"
    assert "text_generation" in cap.metadata.required_providers
    assert "generate" in cap.supported_actions()
    assert "summarize" in cap.supported_actions()


def test_store_document_capability_metadata():
    from capabilities.reference.store_document_capability import StoreDocumentCapability

    cap = StoreDocumentCapability()
    assert cap.category == "storage"
    assert "document_storage" in cap.metadata.required_providers
    assert "store" in cap.supported_actions()
    assert "retrieve" in cap.supported_actions()


def test_send_message_capability_metadata():
    from capabilities.reference.send_message_capability import SendMessageCapability

    cap = SendMessageCapability()
    assert cap.category == "messaging"
    assert "messaging" in cap.metadata.required_providers
    assert "send" in cap.supported_actions()
    assert "broadcast" in cap.supported_actions()


def test_reference_capability_no_provider_graceful_failure():
    """When no provider is registered, capability should return failure result, not raise."""
    from capabilities.reference.generate_text_capability import GenerateTextCapability

    cap = GenerateTextCapability()
    ctx = CapabilityContext()
    result = cap.execute_safe("generate", {"prompt": "hello"}, ctx)
    # Either success (if echo providers registered) or graceful failure
    assert isinstance(result, CapabilityResult)
    assert result.capability_name == "generate_text"


def test_reference_capability_registers_in_registry():
    from capabilities.reference.generate_text_capability import GenerateTextCapability
    from capabilities.reference.send_message_capability import SendMessageCapability
    from capabilities.reference.store_document_capability import StoreDocumentCapability

    RuntimeCapabilityRegistry.register(GenerateTextCapability())
    RuntimeCapabilityRegistry.register(StoreDocumentCapability())
    RuntimeCapabilityRegistry.register(SendMessageCapability())
    RuntimeCapabilityRegistry.enable("generate_text")
    RuntimeCapabilityRegistry.enable("store_document")
    RuntimeCapabilityRegistry.enable("send_message")

    assert RuntimeCapabilityRegistry.get("generate_text") is not None
    assert RuntimeCapabilityRegistry.get("store_document") is not None
    assert RuntimeCapabilityRegistry.get("send_message") is not None

    listed = RuntimeCapabilityRegistry.list_enabled()
    names = [c["name"] for c in listed]
    assert "generate_text" in names
    assert "store_document" in names
    assert "send_message" in names


def test_plan_executor_cancellation():
    """Verify that PlanExecutor respects cancel_requested flags and aborts cleanly."""
    from runtime.plan_executor.executor import PlanExecutor
    from runtime.plan_executor.executor_state import ExecutorState, ExecutorStatus
    from runtime.contracts import ExecutionPlan, PlanStep

    # Define a 3-step plan
    step1 = PlanStep(step_id="s1", action="echo", params={"channel": "test"})
    step2 = PlanStep(step_id="s2", action="echo", params={"channel": "test"})
    step3 = PlanStep(step_id="s3", action="echo", params={"channel": "test"})
    plan = ExecutionPlan(plan_id="p1", intent_type="test", steps=[step1, step2, step3])

    # Run execution with cancellation request pre-set
    cancelled_state = ExecutorState(cancel_requested=True)
    out_state = PlanExecutor.execute_plan(plan, existing_state=cancelled_state)
    
    assert out_state.status == ExecutorStatus.CANCELLED
    assert out_state.current_step_index == 0

    # Test request_cancel transition
    state = ExecutorState(status=ExecutorStatus.RUNNING)
    PlanExecutor.request_cancel(state)
    assert state.cancel_requested is True
    assert state.status == ExecutorStatus.CANCELLING

    # Test request_cancel when waiting for approval
    state = ExecutorState(status=ExecutorStatus.WAITING_APPROVAL)
    PlanExecutor.request_cancel(state)
    assert state.cancel_requested is True
    assert state.status == ExecutorStatus.CANCELLED


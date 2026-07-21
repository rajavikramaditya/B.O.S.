"""Tests for TASK-059 to TASK-066: Configuration Framework."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from config import (
    BaseConfiguration,
    ConfigurationContext,
    ConfigurationLoader,
    ConfigurationMetadata,
    ConfigurationResolver,
    ConfigurationScope,
    FeatureFlagManager,
    RuntimeConfigurationRegistry,
    SecretManager,
    SecretReference,
    SecretResolver,
)
from config.reference import GeminiProviderConfig, WhatsAppProviderConfig


def setup_function():
    RuntimeConfigurationRegistry.clear()
    SecretResolver.clear()
    FeatureFlagManager.clear()


def test_configuration_registration_and_6tier_resolution():
    # Global Config
    global_meta = ConfigurationMetadata(name="app_settings", scope=ConfigurationScope.GLOBAL)
    global_cfg = GeminiProviderConfig()
    global_cfg.metadata = global_meta
    global_cfg.set("timeout", 30)
    RuntimeConfigurationRegistry.register(global_cfg)

    # Tenant Override Config
    tenant_meta = ConfigurationMetadata(name="app_settings", scope=ConfigurationScope.TENANT, tenant_id="tenant_alpha")
    tenant_cfg = GeminiProviderConfig()
    tenant_cfg.metadata = tenant_meta
    tenant_cfg.set("timeout", 60)
    RuntimeConfigurationRegistry.register(tenant_cfg)

    # Global resolution
    res_global = ConfigurationResolver.resolve_value("app_settings", "timeout")
    assert res_global == 30

    # Tenant resolution
    ctx = ConfigurationContext(tenant_id="tenant_alpha")
    res_tenant = ConfigurationResolver.resolve_value("app_settings", "timeout", context=ctx)
    assert res_tenant == 60


def test_secrets_manager_masking_and_injection():
    SecretManager.set_secret("GEMINI_KEY", "secret_api_key_xyz_123")

    ref = SecretReference(key="GEMINI_KEY")
    assert "secret_api_key_xyz_123" not in str(ref)
    assert "***REDACTED***" in str(ref)

    resolved_val = SecretManager.get_secret("GEMINI_KEY")
    assert resolved_val == "secret_api_key_xyz_123"

    injected = SecretManager.inject_secrets({"key_ref": ref, "token": "SECRET::GEMINI_KEY"})
    assert injected["key_ref"] == "secret_api_key_xyz_123"
    assert injected["token"] == "secret_api_key_xyz_123"


def test_feature_flag_manager():
    FeatureFlagManager.enable_flag("beta_search")
    assert FeatureFlagManager.is_enabled("beta_search") is True

    FeatureFlagManager.set_tenant_flag("tenant_a", "beta_search", False)
    assert FeatureFlagManager.is_enabled("beta_search", tenant_id="tenant_a") is False
    assert FeatureFlagManager.is_enabled("beta_search", tenant_id="tenant_b") is True


def test_json_and_yaml_configuration_loader():
    json_str = '{"model": "gpt-4o", "temperature": 0.5}'
    cfg_json = ConfigurationLoader.load_json(json_str, name="openai_json")

    assert cfg_json.get("model") == "gpt-4o"
    assert cfg_json.get("temperature") == 0.5

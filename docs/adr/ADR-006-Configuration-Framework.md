# ADR-006: Centralized Configuration & Secrets Framework

## Context
In B.O.S. (Business Operating System), components, providers, modules, and services must never read raw `.env` files or hardcode environment variables directly. Configuration options, secret tokens, feature flags, and tenant overrides must pass through a unified, stage-gated Configuration Framework.

## Decision
We establish the `backend/config/` framework:
1. **Base Configuration Contract**: All normalized configuration objects inherit from `BaseConfiguration` (`backend/config/base/base_configuration.py`), declaring `ConfigurationMetadata`, `ConfigurationContext`, `ConfigurationScope` (GLOBAL, TENANT, MODULE, PROVIDER, RUNTIME), and `ConfigurationSource`.
2. **Runtime Configuration Registry**: `RuntimeConfigurationRegistry` (`backend/config/registry.py`) manages configuration objects, scope keying, and value overrides.
3. **Configuration Loader**: `ConfigurationLoader` (`backend/config/loader.py`) parses `.env`, OS environment variables, JSON, and YAML sources into normalized `BaseConfiguration` instances without exposing raw file handles.
4. **Secrets Framework**: `SecretManager`, `SecretResolver`, and `SecretReference` (`backend/config/secrets/`) manage secrets securely, masking values in logs (`***REDACTED***`) and injecting resolved secrets into provider configurations at runtime.
5. **Feature Flag Manager**: `FeatureFlagManager` (`backend/config/flags.py`) provides platform-native feature flags supporting global, tenant-specific, and module-specific gradual rollouts.
6. **Hierarchical 6-Tier Resolver**: `ConfigurationResolver` (`backend/config/resolver.py`) resolves values using strict precedence: `Runtime → Tenant → Module → Provider → Global → Default`.
7. **Reference Configurations**: `GeminiProviderConfig`, `OpenAIProviderConfig`, and `WhatsAppProviderConfig` (`backend/config/reference/`) demonstrate normalized provider configuration contracts without external API calls.

## Status
ACCEPTED

## Consequences
- Completely eliminates raw `.env` access across providers, modules, and capabilities.
- Prepares B.O.S. for enterprise multi-tenancy and external cloud secret managers (AWS Vault, GCP Secret Manager) without Kernel modifications.
- Guarantees sensitive credentials are redacted in logs and injected securely at runtime.

"""B.O.S. Reference Provider Configurations v0.1

Reference configuration classes for GeminiProviderConfig, OpenAIProviderConfig, and WhatsAppProviderConfig.
No external API calls.
"""

from typing import Any, Dict
from ..base.base_configuration import BaseConfiguration
from ..base.configuration_metadata import ConfigurationMetadata
from ..base.configuration_scope import ConfigurationScope
from ..secrets.secret_reference import SecretReference


class GeminiProviderConfig(BaseConfiguration):
    """Reference configuration for Gemini AI Provider."""

    def __init__(self, api_key_ref: str = "GEMINI_API_KEY", model: str = "gemini-1.5-flash"):
        meta = ConfigurationMetadata(name="gemini_provider", scope=ConfigurationScope.PROVIDER)
        values = {
            "api_key": SecretReference(key=api_key_ref),
            "model": model,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        super().__init__(meta, values)

    def validate(self) -> bool:
        return bool(self.get("model"))


class OpenAIProviderConfig(BaseConfiguration):
    """Reference configuration for OpenAI Provider."""

    def __init__(self, api_key_ref: str = "OPENAI_API_KEY", model: str = "gpt-4o"):
        meta = ConfigurationMetadata(name="openai_provider", scope=ConfigurationScope.PROVIDER)
        values = {
            "api_key": SecretReference(key=api_key_ref),
            "model": model,
            "temperature": 0.3,
        }
        super().__init__(meta, values)

    def validate(self) -> bool:
        return bool(self.get("model"))


class WhatsAppProviderConfig(BaseConfiguration):
    """Reference configuration for WhatsApp Gateway Provider."""

    def __init__(self, token_ref: str = "WHATSAPP_TOKEN", phone_id: str = "10001"):
        meta = ConfigurationMetadata(name="whatsapp_provider", scope=ConfigurationScope.PROVIDER)
        values = {
            "token": SecretReference(key=token_ref),
            "phone_number_id": phone_id,
            "api_version": "v18.0",
        }
        super().__init__(meta, values)

    def validate(self) -> bool:
        return bool(self.get("phone_number_id"))

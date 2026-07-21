"""B.O.S. Reference Provider Configuration Package v0.1

Provides GeminiProviderConfig, OpenAIProviderConfig, and WhatsAppProviderConfig.
"""

from .provider_configs import (
    GeminiProviderConfig,
    OpenAIProviderConfig,
    WhatsAppProviderConfig,
)

__all__ = [
    "GeminiProviderConfig",
    "OpenAIProviderConfig",
    "WhatsAppProviderConfig",
]

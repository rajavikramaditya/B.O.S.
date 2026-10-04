"""B.O.S. Platform Bootstrap v1.0

Composition root: wires stores, providers, adapters and capabilities together at
startup. This is the only place that knows concrete implementations; everything
else talks to registries and contracts.
"""

import logging
from typing import Any, Dict, List, Optional

from adapters.messaging import EmailAdapter, TelegramAdapter, WhatsAppAdapter
from adapters.registry import AdapterRegistry
from capabilities.core.catalog import build_core_capabilities, declare_reference_capabilities
from capabilities.reference import GenerateTextCapability, SendMessageCapability
from capabilities.registry import RuntimeCapabilityRegistry
from integrations.connections import ConnectionStore
from providers.ai.claude_provider import ClaudeProvider
from providers.ai.gemini_provider import GeminiProvider
from providers.base.base_provider import BaseProvider
from providers.base.provider_context import ProviderContext
from providers.webhooks.webhook_event_provider import WebhookEventProvider
from providers.memory.sql_memory_provider import SqlMemoryProvider
from providers.messaging.channel_messaging_provider import ChannelMessagingProvider
from providers.records.workspace_context_provider import WorkspaceContextProvider
from providers.records.workspace_records_provider import WorkspaceRecordsProvider
from providers.registry import RuntimeProviderRegistry
from workspace.database import WorkspaceDatabase
from workspace.models import Owner
from workspace.settings_store import BUSINESS_PROFILE, SettingsStore
from workspace.vault import WorkspaceVault

from .settings import PlatformSettings

logger = logging.getLogger("bos.platform")

VERSION = "1.0.0"


class Platform:
    """Process-wide platform state assembled once at startup."""

    settings: Optional[PlatformSettings] = None
    ai_providers: Dict[str, Any] = {}
    scheduler: Any = None

    @classmethod
    def start(cls, settings: PlatformSettings, start_scheduler: bool = True) -> None:
        cls.settings = settings
        WorkspaceDatabase.configure(settings.database_url)
        WorkspaceVault.configure(settings.secret_key)

        cls._register_providers(settings)
        cls._register_adapters()
        cls._register_capabilities()
        cls.refresh_ai_providers()

        if start_scheduler and settings.autopilot_scheduler_enabled:
            from autopilot.scheduler import AutopilotScheduler

            cls.scheduler = AutopilotScheduler(settings.autopilot_interval_minutes, cls.is_ready)
            cls.scheduler.start()
        logger.info("B.O.S. %s started (%s)", VERSION, settings.environment)

    @classmethod
    def stop(cls) -> None:
        if cls.scheduler:
            cls.scheduler.stop()
        for name in ("sql_memory",):
            provider = RuntimeProviderRegistry.get_provider(name)
            if provider:
                provider.shutdown()
        WorkspaceDatabase.dispose()

    # ------------------------------------------------------------------ wiring

    @classmethod
    def _register_providers(cls, settings: PlatformSettings) -> None:
        claude = ClaudeProvider(lambda: cls._ai_key("anthropic"), model=settings.anthropic_model)
        gemini = GeminiProvider(lambda: cls._ai_key("gemini"), model=settings.gemini_model)
        cls.ai_providers = {"anthropic": claude, "gemini": gemini}
        providers: List[BaseProvider] = [
            claude,
            gemini,
            SqlMemoryProvider(settings.memory_database_url),
            WorkspaceRecordsProvider(),
            WorkspaceContextProvider(),
            ChannelMessagingProvider(),
            WebhookEventProvider(),
        ]
        for provider in providers:
            RuntimeProviderRegistry.register(provider)
            provider.initialize(ProviderContext(provider_id=provider.metadata.name, environment=settings.environment))

    @staticmethod
    def _register_adapters() -> None:
        for adapter in (
            TelegramAdapter(credentials=lambda: ConnectionStore.credentials("telegram")),
            WhatsAppAdapter(credentials=lambda: ConnectionStore.credentials("whatsapp")),
            EmailAdapter(credentials=lambda: ConnectionStore.credentials("email")),
        ):
            AdapterRegistry.register(adapter)

    @staticmethod
    def _register_capabilities() -> None:
        generate_text = GenerateTextCapability()
        send_message = SendMessageCapability()
        declare_reference_capabilities(generate_text, send_message)
        for capability in [generate_text, send_message, *build_core_capabilities()]:
            RuntimeCapabilityRegistry.register(capability)

    # ------------------------------------------------------------------ AI

    @classmethod
    def _ai_key(cls, connector_id: str) -> str:
        """A key saved from the dashboard wins over the environment variable."""
        saved = ConnectionStore.credentials(connector_id).get("api_key", "") if WorkspaceDatabase.is_configured() else ""
        if saved:
            return saved
        if cls.settings is None:
            return ""
        return cls.settings.anthropic_api_key if connector_id == "anthropic" else cls.settings.gemini_api_key

    @classmethod
    def refresh_ai_providers(cls) -> None:
        """Enable only configured AI providers, preferred one first."""
        preferred = (cls.settings.ai_provider if cls.settings else "auto") or "auto"
        for connector_id, provider in cls.ai_providers.items():
            configured = provider.is_configured()
            if preferred not in ("auto", connector_id) and configured:
                # Keep the non-preferred provider as a backup behind the preferred one.
                provider.metadata.priority = 50
            if configured:
                RuntimeProviderRegistry.enable_provider(provider.metadata.name)
            else:
                RuntimeProviderRegistry.disable_provider(provider.metadata.name)

    @classmethod
    def ai_status(cls) -> Dict[str, Any]:
        active = [
            {"id": cid, "provider": p.metadata.name, "model": p.model}
            for cid, p in sorted(cls.ai_providers.items(), key=lambda kv: kv[1].metadata.priority)
            if p.is_configured()
        ]
        return {"configured": bool(active), "active": active[0] if active else None, "available": active}

    # ------------------------------------------------------------------ readiness

    @staticmethod
    def has_owner() -> bool:
        with WorkspaceDatabase.session() as db:
            return db.query(Owner.id).first() is not None

    @classmethod
    def is_ready(cls) -> bool:
        profile = SettingsStore.get(BUSINESS_PROFILE)
        return cls.has_owner() and bool(profile.get("name")) and cls.ai_status()["configured"]

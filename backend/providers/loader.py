"""B.O.S. Provider Loader v0.1

Validates manifest, instantiates provider, injects service context, and registers with RuntimeProviderRegistry.
"""

from typing import Any, Dict, Type
from .base.base_provider import BaseProvider
from .base.manifest import ProviderManifest
from .base.provider_context import ProviderContext
from .registry import RuntimeProviderRegistry
from .events import ProviderEventPublisher, ProviderEventType


class ProviderLoader:
    """Loader handling provider validation, initialization, and registration."""

    @classmethod
    def load_from_manifest(
        cls,
        manifest: ProviderManifest,
        provider_class: Type[BaseProvider],
        services: Dict[str, Any] | None = None,
        config: Dict[str, Any] | None = None,
    ) -> BaseProvider:
        metadata = manifest.to_metadata()
        if config:
            metadata.config.update(config)

        provider_instance = provider_class(metadata)

        ctx = ProviderContext(
            provider_id=f"prov_{metadata.name.lower()}",
            services=services or {},
            config=metadata.config,
        )

        provider_instance.initialize(ctx)
        RuntimeProviderRegistry.register(provider_instance)
        ProviderEventPublisher.publish(ProviderEventType.PROVIDER_LOADED, metadata.name, metadata.to_dict())

        return provider_instance

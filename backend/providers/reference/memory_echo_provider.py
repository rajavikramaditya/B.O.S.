"""B.O.S. Reference Memory Echo Provider v0.1

Dummy reference provider implementing the 'echo' capability with priority 20.
"""

from typing import Any, Dict
from ..base.base_provider import BaseProvider
from ..base.provider_metadata import ProviderMetadata
from ..base.provider_context import ProviderContext


class MemoryEchoProvider(BaseProvider):
    """Reference provider offering secondary fallback echo processing."""

    def __init__(self, metadata: ProviderMetadata | str | None = None, name: str = "MemoryEchoProvider", priority: int = 20):
        if isinstance(metadata, ProviderMetadata):
            meta = metadata
        else:
            p_name = metadata if isinstance(metadata, str) else name
            meta = ProviderMetadata(
                name=p_name,
                capability="echo",
                priority=priority,
                description="Fallback memory echo provider.",
            )
        super().__init__(meta)

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "provider": self.metadata.name,
            "action": action,
            "echo_output": f"[MemoryEcho] {params.get('text', '')}",
        }

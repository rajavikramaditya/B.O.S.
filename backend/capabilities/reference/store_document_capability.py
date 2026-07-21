"""B.O.S. StoreDocumentCapability v0.1

Reference capability for document and memory storage.
Delegates all execution to ProviderResolver — never calls databases directly.
"""

from typing import Any, Dict, List

from capabilities.base.base_capability import BaseCapability
from capabilities.base.capability_context import CapabilityContext
from capabilities.base.capability_metadata import CapabilityMetadata
from capabilities.base.capability_result import CapabilityResult
from capabilities.base.capability_scope import CapabilityScope


class StoreDocumentCapability(BaseCapability):
    """Platform capability for document and memory storage.

    Business Modules may store and retrieve documents without knowing
    which storage provider (PostgreSQL, SQLite, S3) will execute it.
    """

    def __init__(self):
        super().__init__(
            metadata=CapabilityMetadata(
                name="store_document",
                version="1.0.0",
                category="storage",
                description="Document and memory storage, retrieval, and deletion.",
                required_providers=["document_storage"],
                permissions=[],
                scope=CapabilityScope.GLOBAL,
            )
        )

    def supported_actions(self) -> List[str]:
        return ["store", "retrieve", "delete", "search"]

    def execute(
        self, action: str, params: Dict[str, Any], context: CapabilityContext
    ) -> CapabilityResult:
        """Delegate execution to ProviderResolver — never calls storage directly."""
        try:
            from providers.resolver import ProviderResolver

            result = ProviderResolver.execute_capability(
                capability="document_storage",
                action=action,
                params=params,
            )
            return CapabilityResult(
                success=result.get("success", False),
                capability_name=self.name,
                action=action,
                data=result,
                message=result.get("message", ""),
                error=result.get("error"),
                provider_used=result.get("resolved_provider"),
                correlation_id=context.correlation_id,
            )
        except Exception as ex:
            return CapabilityResult.failure(
                capability_name=self.name,
                action=action,
                error=f"StoreDocumentCapability execution failed: {str(ex)}",
                correlation_id=context.correlation_id,
            )

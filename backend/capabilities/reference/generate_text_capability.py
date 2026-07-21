"""B.O.S. GenerateTextCapability v0.1

Reference capability for LLM-based text generation.
Delegates all execution to ProviderResolver — never calls LLM APIs directly.
"""

from typing import Any, Dict, List

from capabilities.base.base_capability import BaseCapability
from capabilities.base.capability_context import CapabilityContext
from capabilities.base.capability_metadata import CapabilityMetadata
from capabilities.base.capability_result import CapabilityResult
from capabilities.base.capability_scope import CapabilityScope


class GenerateTextCapability(BaseCapability):
    """Platform capability for LLM-based text generation and summarization.

    Business Modules may request text generation without knowing
    which LLM provider (Gemini, OpenAI, Ollama) will execute it.
    """

    def __init__(self):
        super().__init__(
            metadata=CapabilityMetadata(
                name="generate_text",
                version="1.0.0",
                category="ai",
                description="LLM-based text generation, summarization, and transformation.",
                required_providers=["text_generation"],
                permissions=[],
                scope=CapabilityScope.GLOBAL,
            )
        )

    def supported_actions(self) -> List[str]:
        return ["generate", "summarize", "transform"]

    def execute(
        self, action: str, params: Dict[str, Any], context: CapabilityContext
    ) -> CapabilityResult:
        """Delegate execution to ProviderResolver — never calls LLM directly."""
        try:
            from providers.resolver import ProviderResolver

            result = ProviderResolver.execute_capability(
                capability="text_generation",
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
                error=f"GenerateTextCapability execution failed: {str(ex)}",
                correlation_id=context.correlation_id,
            )

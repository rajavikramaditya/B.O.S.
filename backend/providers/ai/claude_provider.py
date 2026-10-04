"""B.O.S. Claude Provider v1.0

`text_generation` provider backed by Anthropic Claude.
The API key is resolved per call, so a key added from the dashboard works without restart.
"""

from typing import Any, Callable, Dict, Optional

import anthropic

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata
from .text_generation import SUPPORTED_ACTIONS, TEXT_GENERATION, TextGenerationRequest, build_result, failure

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeProvider(BaseProvider):
    """Anthropic Claude implementation of the text generation contract."""

    def __init__(self, api_key_resolver: Callable[[], str], model: str = "claude-opus-5-5", priority: int = 10):
        super().__init__(
            ProviderMetadata(
                name="claude",
                capability=TEXT_GENERATION,
                priority=priority,
                description="Anthropic Claude language models.",
                config={"model": model},
            )
        )
        self._resolve_key = api_key_resolver
        self.model = model
        self._client: Optional[anthropic.Anthropic] = None
        self._client_key = ""

    def is_configured(self) -> bool:
        return bool(self._resolve_key())

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        self._client = None

    @staticmethod
    def verify_key(key: str) -> Optional[str]:
        """Return None when the key works, otherwise a human-readable problem."""
        try:
            anthropic.Anthropic(api_key=key, max_retries=1, timeout=20.0).models.list(limit=1)
            return None
        except anthropic.AuthenticationError:
            return "Claude rejected this API key."
        except anthropic.APIConnectionError:
            return "Could not reach the Claude API."
        except anthropic.APIStatusError as ex:
            return f"Claude API error {ex.status_code}."

    def _client_for(self, key: str) -> anthropic.Anthropic:
        if self._client is None or key != self._client_key:
            self._client = anthropic.Anthropic(api_key=key, max_retries=2, timeout=180.0)
            self._client_key = key
        return self._client

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action not in SUPPORTED_ACTIONS:
            return failure(self.metadata.name, f"Unsupported action '{action}'.")
        key = self._resolve_key()
        if not key:
            return failure(self.metadata.name, "Claude API key is not configured.")

        req = TextGenerationRequest.from_params(action, params)
        output_config: Dict[str, Any] = {"effort": req.effort}
        if req.json_schema:
            output_config["format"] = {"type": "json_schema", "schema": req.json_schema}

        try:
            response = self._client_for(key).beta.messages.create(
                model=self.model,
                max_tokens=req.max_tokens,
                system=req.system or anthropic.omit,
                messages=req.messages,
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            return failure(self.metadata.name, "Claude rejected the API key.")
        except anthropic.RateLimitError:
            return failure(self.metadata.name, "Claude rate limit reached. Please retry shortly.")
        except anthropic.APIStatusError as ex:
            return failure(self.metadata.name, f"Claude API error {ex.status_code}: {ex.message}")
        except anthropic.APIConnectionError:
            return failure(self.metadata.name, "Could not reach the Claude API.")

        if response.stop_reason == "refusal":
            return failure(self.metadata.name, "Claude declined this request.")
        text = "".join(block.text for block in response.content if block.type == "text")
        return build_result(
            provider=self.metadata.name,
            model=response.model,
            text=text,
            stop_reason=str(response.stop_reason),
            wants_json=bool(req.json_schema),
        )

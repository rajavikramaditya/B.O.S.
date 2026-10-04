"""B.O.S. Gemini Provider v1.0

`text_generation` provider backed by Google Gemini.
"""

from typing import Any, Callable, Dict, Optional

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata
from .text_generation import SUPPORTED_ACTIONS, TEXT_GENERATION, TextGenerationRequest, build_result, failure


class GeminiProvider(BaseProvider):
    """Google Gemini implementation of the text generation contract."""

    def __init__(self, api_key_resolver: Callable[[], str], model: str = "gemini-3.5-flash-lite", priority: int = 20):
        super().__init__(
            ProviderMetadata(
                name="gemini",
                capability=TEXT_GENERATION,
                priority=priority,
                description="Google Gemini language models.",
                config={"model": model},
            )
        )
        self._resolve_key = api_key_resolver
        self.model = model
        self._client: Optional[Any] = None
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
        from google import genai
        from google.genai import errors

        try:
            next(iter(genai.Client(api_key=key).models.list(config={"page_size": 1})), None)
            return None
        except errors.APIError as ex:
            return f"Gemini rejected this key ({ex.code})."
        except Exception:
            return "Could not reach the Gemini API."

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action not in SUPPORTED_ACTIONS:
            return failure(self.metadata.name, f"Unsupported action '{action}'.")
        key = self._resolve_key()
        if not key:
            return failure(self.metadata.name, "Gemini API key is not configured.")

        from google import genai
        from google.genai import errors, types

        if self._client is None or key != self._client_key:
            self._client = genai.Client(api_key=key)
            self._client_key = key

        req = TextGenerationRequest.from_params(action, params)
        contents = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
            for m in req.messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=req.system or None,
            max_output_tokens=req.max_tokens,
            response_mime_type="application/json" if req.json_schema else None,
            response_json_schema=req.json_schema or None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except errors.APIError as ex:
            return failure(self.metadata.name, f"Gemini API error {ex.code}: {ex.message}")
        except Exception as ex:  # network and transport errors
            return failure(self.metadata.name, f"Could not reach Gemini: {ex}")

        finish = ""
        if response.candidates:
            finish = str(response.candidates[0].finish_reason or "")
        return build_result(
            provider=self.metadata.name,
            model=self.model,
            text=response.text or "",
            stop_reason=finish,
            wants_json=bool(req.json_schema),
        )

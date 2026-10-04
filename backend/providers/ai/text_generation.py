"""B.O.S. Text Generation Provider Contract v1.0

Shared request/response shape for every `text_generation` provider, so the
Runtime and capabilities never depend on a specific LLM vendor.

Request params (action "generate" | "summarize" | "transform"):
    system:       str             — instructions
    messages:     [{role, content}] — "user" / "assistant" turns
    json_schema:  dict | None     — when set, the reply must be JSON matching it
    max_tokens:   int
    effort:       "low" | "medium" | "high"

Response:
    {success, text, data, model, provider, stop_reason, error}
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TEXT_GENERATION = "text_generation"
SUPPORTED_ACTIONS = ("generate", "summarize", "transform")


@dataclass
class TextGenerationRequest:
    system: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    json_schema: Optional[Dict[str, Any]] = None
    max_tokens: int = 4000
    effort: str = "medium"

    @classmethod
    def from_params(cls, action: str, params: Dict[str, Any]) -> "TextGenerationRequest":
        messages = params.get("messages")
        if not messages:
            text = str(params.get("text") or params.get("prompt") or "")
            if action == "summarize":
                text = f"Summarize the following clearly and briefly:\n\n{text}"
            messages = [{"role": "user", "content": text}]
        clean = [
            {"role": "assistant" if m.get("role") == "assistant" else "user", "content": str(m.get("content") or "")}
            for m in messages
            if str(m.get("content") or "").strip()
        ]
        if not clean or clean[0]["role"] != "user":
            clean.insert(0, {"role": "user", "content": "(conversation start)"})
        return cls(
            system=str(params.get("system") or ""),
            messages=_merge_consecutive(clean),
            json_schema=params.get("json_schema"),
            max_tokens=int(params.get("max_tokens") or 4000),
            effort=str(params.get("effort") or "medium"),
        )


def _merge_consecutive(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """LLM APIs expect alternating roles; join consecutive same-role turns."""
    merged: List[Dict[str, str]] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1] = {"role": m["role"], "content": f"{merged[-1]['content']}\n\n{m['content']}"}
        else:
            merged.append(dict(m))
    return merged


def build_result(
    *,
    provider: str,
    model: str,
    text: str,
    stop_reason: str,
    wants_json: bool,
) -> Dict[str, Any]:
    data = None
    if wants_json:
        try:
            data = json.loads(text)
        except ValueError:
            return {
                "success": False,
                "provider": provider,
                "model": model,
                "text": text,
                "stop_reason": stop_reason,
                "error": "Model reply was not valid JSON.",
            }
    return {
        "success": True,
        "provider": provider,
        "model": model,
        "text": text,
        "data": data,
        "stop_reason": stop_reason,
    }


def failure(provider: str, error: str) -> Dict[str, Any]:
    return {"success": False, "provider": provider, "error": error}

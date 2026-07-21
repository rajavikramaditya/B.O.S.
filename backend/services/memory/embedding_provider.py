from __future__ import annotations

import logging
from typing import Any

import requests
import urllib3

from services.llm.provider_router import _safe_error_summary, get_gemini_api_key
from services.safety.security_config import get_ssl_verify


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

PRIMARY_EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_FALLBACK_MODE = "keyword_only"
EMBEDDING_RETRIEVAL_ENABLED = True


def _short_error_text(text: str, limit: int = 220) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def embed_text(text: str) -> dict[str, Any]:
    """
    Generate an embedding vector for approved memory text.

    This provider does not generate replies and does not store vectors itself.
    Vectors are persisted by the Postgres memory repository and used for pgvector
    semantic retrieval. Callers must decide separately whether a memory write is
    owner-approved.
    """
    cleaned = (text or "").strip()
    base: dict[str, Any] = {
        "status": "not_started",
        "model": PRIMARY_EMBEDDING_MODEL,
        "vector": None,
        "vector_length": 0,
        "error": None,
        "fallback_mode": EMBEDDING_FALLBACK_MODE,
        "semantic_retrieval_enabled": EMBEDDING_RETRIEVAL_ENABLED,
    }

    if not cleaned:
        base.update(
            {
                "status": "empty_input",
                "error": "embedding_input_empty",
            }
        )
        return base

    api_key = get_gemini_api_key()
    if not api_key:
        base.update(
            {
                "status": "unavailable",
                "error": "gemini_api_key_missing",
            }
        )
        return base

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{PRIMARY_EMBEDDING_MODEL}:embedContent?key={api_key}"
    )
    payload = {
        "model": f"models/{PRIMARY_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": cleaned}]},
    }

    try:
        res = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10.0,
            verify=get_ssl_verify(),
        )
        if res.status_code != 200:
            base.update(
                {
                    "status": "error",
                    "error": f"http_{res.status_code}: {_short_error_text(res.text)}",
                }
            )
            return base

        data = res.json()
        values = data.get("embedding", {}).get("values")
        if not isinstance(values, list) or not values:
            base.update(
                {
                    "status": "error",
                    "error": "embedding_vector_missing",
                }
            )
            return base

        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError):
            base.update(
                {
                    "status": "error",
                    "error": "embedding_vector_invalid",
                }
            )
            return base

        base.update(
            {
                "status": "success",
                "vector": vector,
                "vector_length": len(vector),
                "error": None,
            }
        )
        return base
    except Exception as exc:
        reason = _safe_error_summary(exc)
        logger.warning("Embedding provider failed: %s", reason)
        base.update(
            {
                "status": "error",
                "error": reason,
            }
        )
        return base


__all__ = [
    "PRIMARY_EMBEDDING_MODEL",
    "EMBEDDING_FALLBACK_MODE",
    "EMBEDDING_RETRIEVAL_ENABLED",
    "embed_text",
]

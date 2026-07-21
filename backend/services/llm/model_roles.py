"""M4-A8.2-A — Approved model role map (quota-safe normal Neena flow).

Two working text models only:
  - Primary: fast Gemma 26B-class (API: gemma-4-26b-a4b-it; AI Studio may show Gemma 2 26B)
  - Light/fallback/creative: gemini-3.1-flash-lite
Gemma 4 31B is disallowed in normal flow (slow + burns quota).
"""
from __future__ import annotations

from typing import Any

# Low-quota / unintended models — never used in normal runtime flow.
DISALLOWED_NORMAL_FLOW_API_IDS = frozenset(
    {
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.5-flash-preview",
        "gemini-2.5-flash-preview-tts",
        "gemma-4-31b-it",
        "gemma-4-31b",
    }
)

MODEL_ROLE_KEYS = (
    "COMMAND_INTERPRETER_MODEL",
    "CONVERSATION_MODEL",
    "CREATIVE_MODEL",
    "MEMORY_EMBEDDING_MODEL",
    "TTS_MODEL",
    "FALLBACK_MODEL",
)

# Owner: fast 26B primary for intent/chat/agent-step; Lite for creative + fallback.
MODEL_ROLE_CONFIG: dict[str, dict[str, Any]] = {
    "COMMAND_INTERPRETER_MODEL": {
        "primary_option": "gemini-3.1-flash-lite",
        "candidate_api_ids": [
            "gemini-3.1-flash-lite",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash",
        ],
        "fallback_option": "gemma-2-26b",
    },
    "CONVERSATION_MODEL": {
        "primary_option": "gemini-3.1-flash-lite",
        "candidate_api_ids": [
            "gemini-3.1-flash-lite",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash",
        ],
        "fallback_option": "gemma-2-26b",
    },
    "CREATIVE_MODEL": {
        "primary_option": "gemini-3.1-flash-lite",
        "candidate_api_ids": [
            "gemini-3.1-flash-lite",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash",
        ],
        "fallback_option": "gemma-2-26b",
    },
    "FALLBACK_MODEL": {
        "primary_option": "gemma-2-26b",
        "candidate_api_ids": [
            "gemma-4-26b-a4b-it",
            "gemma-2-26b-it",
            "gemma-2-27b-it",
        ],
        "fallback_option": "gemini-3.1-flash-lite",
    },
    "MEMORY_EMBEDDING_MODEL": {
        "api_id": "gemini-embedding-2",
    },
    "TTS_MODEL": {
        "api_ids": ["gemini-3.1-flash-tts-preview"],
    },
}

# Config-approved API ids when live list cache is empty (no 2.5 / 3.5 flash / 31B).
CONFIG_APPROVED_API_IDS = [
    "gemini-3.1-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemma-4-26b-a4b-it",
    "gemma-2-26b-it",
    "gemma-2-27b-it",
    "gemini-embedding-2",
    "gemini-3.1-flash-tts-preview",
]


def is_disallowed_normal_flow(api_id: str | None) -> bool:
    if not api_id:
        return False
    base = api_id.strip().lower()
    if base in DISALLOWED_NORMAL_FLOW_API_IDS:
        return True
    if "gemini-2.5-flash" in base and "tts" not in base:
        return True
    if "gemini-3.5-flash" in base:
        return True
    if "gemma-4-31b" in base:
        return True
    return False


def _first_allowed(candidates: list[str], available: set[str]) -> str | None:
    for cid in candidates:
        if cid in available and not is_disallowed_normal_flow(cid):
            return cid
    return None


def resolve_role_to_api_id(role: str, available: set[str]) -> str | None:
    """Pick first approved API model id for role from cached/config availability."""
    cfg = MODEL_ROLE_CONFIG.get(role)
    if not cfg:
        return None
    if role == "MEMORY_EMBEDDING_MODEL":
        api_id = cfg.get("api_id")
        return api_id if api_id and not is_disallowed_normal_flow(api_id) else None
    candidates = list(cfg.get("candidate_api_ids") or [])
    hit = _first_allowed(candidates, available)
    if hit:
        return hit
    fb_option = cfg.get("fallback_option")
    if fb_option:
        from services.llm.provider_router import get_model_candidates

        fb_candidates = get_model_candidates(fb_option)
        return _first_allowed(fb_candidates, available)
    return None


def get_public_role_map() -> dict[str, Any]:
    """Safe role map for tests/docs (no secrets)."""
    out: dict[str, Any] = {}
    for role in MODEL_ROLE_KEYS:
        cfg = MODEL_ROLE_CONFIG.get(role, {})
        if role == "MEMORY_EMBEDDING_MODEL":
            out[role] = cfg.get("api_id")
        elif role == "TTS_MODEL":
            out[role] = list(cfg.get("api_ids") or [])
        else:
            out[role] = {
                "primary_option": cfg.get("primary_option"),
                "candidate_api_ids": list(cfg.get("candidate_api_ids") or []),
                "fallback_option": cfg.get("fallback_option"),
            }
    out["disallowed_normal_flow"] = sorted(DISALLOWED_NORMAL_FLOW_API_IDS)
    return out


__all__ = [
    "CONFIG_APPROVED_API_IDS",
    "DISALLOWED_NORMAL_FLOW_API_IDS",
    "MODEL_ROLE_CONFIG",
    "MODEL_ROLE_KEYS",
    "get_public_role_map",
    "is_disallowed_normal_flow",
    "resolve_role_to_api_id",
]

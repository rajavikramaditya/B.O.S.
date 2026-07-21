"""
Owner-friendly Command Center unlock via env phrase + fuzzy match.

Secrets live in environment only; raw phrases are never logged.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from difflib import SequenceMatcher
from typing import Iterable

SESSION_COOKIE_NAME = "neena_admin_session"

_PHRASE_VARIANTS = (
    ("i am", "main"),
)
_WORD_VARIANTS = {
    "hy": "hi",
    "hey": "hi",
    "mein": "main",
    "mai": "main",
    "me": "main",
    "hu": "hoon",
    "hun": "hoon",
    "nina": "neena",
}
_UNLOCK_STOPWORDS = frozenset({"hello", "hi", "neena", "main", "hoon", "i", "am"})
_WORD_FUZZY_MIN = 0.82

# Common hi-IN speech-to-text Devanagari outputs for owner unlock keywords.
_DEVANAGARI_TO_LATIN_TOKEN: dict[str, str] = {
    "हाय": "hi",
    "हे": "hi",
    "है": "hi",
    "हि": "hi",
    "हाई": "hi",
    "नीना": "neena",
    "निना": "neena",
    "नेणा": "neena",
    "नेना": "neena",
    "आई": "i",
    "ऐ": "i",
    "एम": "am",
    "aim": "am",
    "मैं": "main",
    "मै": "main",
    "मैन": "main",
    "मैंने": "main",
    "विक्रम": "vikram",
    "विक्राम": "vikram",
    "विक्रम": "vikram",
    "कूल": "cool",
    "कुल": "cool",
    "कूल्": "cool",
    "unlock": "unlock",
    "अनलॉक": "unlock",
    "अनलॉक": "unlock",
    
}

# Latin aliases per required unlock keyword (voice STT + Hinglish).
_KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "hi": ("hi", "hy", "hey", "hai", "हाय", "हे", "है", "हि", "hello"),
    "neena": ("neena", "nina", "nena", "नीना", "निना", "नेना"),
    "i": ("i", "ai", "eye", "आई", "ऐ"),
    "am": ("am", "em", "aim", "एम"),
    "main": ("main", "mein", "mai", "may", "मैं", "मै", "मैन"),
    "vikram": ("vikram", "vikram", "विक्रम", "विक्राम"),
    "cool": ("cool", "kool", "kul", "coule", "कूल", "कुल"),
    "unlock": ("unlock", "anlock", "unlock", "अनलॉक"),
    "hoon": ("hoon", "hu", "hun", "हूं", "हूँ", "हु"),
}


def _contains_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in (text or ""))


def _romanize_unlock_token(token: str) -> str:
    raw = (token or "").strip().lower()
    if not raw:
        return ""
    if raw in _DEVANAGARI_TO_LATIN_TOKEN:
        return _DEVANAGARI_TO_LATIN_TOKEN[raw]
    if raw in _WORD_VARIANTS:
        return _WORD_VARIANTS[raw]
    return raw


def _latin_forms_for_required(required: str) -> list[str]:
    key = normalize_unlock_text(required)
    if not key:
        return []
    forms = {key}
    for alias in _KEYWORD_ALIASES.get(key, ()):
        mapped = _romanize_unlock_token(alias)
        if mapped:
            forms.add(mapped)
        norm = normalize_unlock_text(alias)
        if norm:
            forms.add(norm)
    return sorted(forms)


def _token_matches_required(token: str, required: str) -> bool:
    token_raw = (token or "").strip().lower()
    if not token_raw:
        return False
    token_latin = _romanize_unlock_token(token_raw)
    token_norm = normalize_unlock_text(token_latin)
    if not token_norm:
        token_norm = token_latin
    for form in _latin_forms_for_required(required):
        if token_raw == form:
            return True
        if _fuzzy_ratio(token_norm, form) >= _WORD_FUZZY_MIN:
            return True
        if _fuzzy_ratio(token_latin, form) >= _WORD_FUZZY_MIN:
            return True
    return False


def unlock_phrase_configured() -> bool:
    return bool((os.environ.get("ADMIN_UNLOCK_PHRASE") or "").strip())


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def unlock_min_score() -> float:
    return _env_float("ADMIN_UNLOCK_MIN_SCORE", 0.82)


def unlock_session_days() -> int:
    return _env_int("ADMIN_UNLOCK_SESSION_DAYS", 7)


def normalize_unlock_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"[^\w\s\u0900-\u097f]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    for src, dst in _PHRASE_VARIANTS:
        lowered = lowered.replace(src, dst)
    tokens = []
    for token in lowered.split():
        latin = _romanize_unlock_token(token)
        tokens.append(_WORD_VARIANTS.get(latin, latin))
    return " ".join(tokens)


def _tokenize(text: str) -> list[str]:
    normalized = normalize_unlock_text(text)
    if not normalized:
        return []
    return normalized.split()


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def required_unlock_words() -> list[str]:
    raw = (os.environ.get("ADMIN_UNLOCK_REQUIRED_WORDS") or "").strip()
    if raw:
        return [w.strip().lower() for w in raw.split(",") if w.strip()]
    phrase = (os.environ.get("ADMIN_UNLOCK_PHRASE") or "").strip()
    return [w for w in _tokenize(phrase) if w not in _UNLOCK_STOPWORDS]


def _required_words_present(input_tokens: Iterable[str], required: Iterable[str]) -> bool:
    tokens = list(input_tokens)
    for word in required:
        if not any(_token_matches_required(token, word) for token in tokens):
            return False
    return True


def verify_unlock_phrase(spoken: str) -> tuple[bool, float]:
    expected = (os.environ.get("ADMIN_UNLOCK_PHRASE") or "").strip()
    if not expected:
        return False, 0.0
    normalized_input = normalize_unlock_text(spoken)
    normalized_expected = normalize_unlock_text(expected)
    if not normalized_input or not normalized_expected:
        return False, 0.0
    score = _fuzzy_ratio(normalized_input, normalized_expected)
    required = required_unlock_words()
    words_ok = _required_words_present(normalized_input.split(), required)
    # Voice STT often returns Devanagari / partial phrase text. Required private
    # words are the real gate once romanized; full phrase score is secondary.
    if words_ok and required:
        accepted = True
    else:
        accepted = score >= unlock_min_score() and words_ok
    return accepted, score


def _session_secret() -> str:
    for name in ("ADMIN_SESSION_SECRET", "ADMIN_API_KEY"):
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    phrase = (os.environ.get("ADMIN_UNLOCK_PHRASE") or "").strip()
    if phrase:
        return hashlib.sha256(f"neena-session:{phrase}".encode()).hexdigest()
    return ""


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    secret = _session_secret()
    if not secret:
        raise RuntimeError("Admin session secret not configured")
    expires_at = int(time.time()) + unlock_session_days() * 86400
    payload = str(expires_at)
    signature = _sign_payload(payload, secret)
    return f"{payload}.{signature}"


def verify_session_token(token: str) -> bool:
    secret = _session_secret()
    if not secret or not token:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    payload, signature = parts
    if not payload.isdigit():
        return False
    expected_sig = _sign_payload(payload, secret)
    if not hmac.compare_digest(signature, expected_sig):
        return False
    return int(payload) > int(time.time())


def session_cookie_max_age() -> int:
    return unlock_session_days() * 86400


def cookie_secure_flag() -> bool:
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env in ("development", "local", "test"):
        return False
    explicit = (os.environ.get("ADMIN_SESSION_COOKIE_SECURE") or "").strip().lower()
    if explicit in ("0", "false", "no", "off"):
        return False
    if explicit in ("1", "true", "yes", "on"):
        return True
    return _env_truthy("COMMAND_CENTER_LOCAL_ONLY", "false") is False


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


__all__ = [
    "SESSION_COOKIE_NAME",
    "cookie_secure_flag",
    "create_session_token",
    "normalize_unlock_text",
    "required_unlock_words",
    "session_cookie_max_age",
    "unlock_min_score",
    "unlock_phrase_configured",
    "unlock_session_days",
    "verify_session_token",
    "verify_unlock_phrase",
]

import os
import json
import time
import logging
import requests
import urllib3
import sys
import threading

# Disable insecure request warnings for local environment proxies
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import services.tools.legacy_gemini_registry as tr
import services.safety.policy_guard as policy_guard
import services.memory.adapter as memory_adapter
from services.llm.model_roles import CONFIG_APPROVED_API_IDS, is_disallowed_normal_flow
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

SHORT_SAFE_DELAY_SECONDS = 2.0
# When the secondary model (flash-lite) is on a short cooldown, WAIT instead of
# skipping — dual-model means a real reply should still come; skipping caused
# empty/canned paths even though flash-lite would be free in ~3s.
FALLBACK_COOLDOWN_WAIT_SECONDS = 8.0
MODEL_LIST_NETWORK_TIMEOUT = 5.0
_MODEL_CACHE_LOCK = threading.Lock()

# Frontend display names, internal option values, and actual API IDs are kept separate here.
# Two working text models only: fast Gemma 26B-class + Flash Lite.
# AI Studio may label the fast 26B MoE as "Gemma 2 26B"; Gemini API id is gemma-4-26b-a4b-it.
MODEL_OPTION_CONFIG = {
    "gemini-3.1-flash-lite": {
        "display_name": "Gemini 3.1 Flash Lite",
        "candidate_ids": ["gemini-3.1-flash-lite", "gemini-1.5-flash-8b", "gemini-1.5-flash"],
        "cooldown_seconds": 4.0,
    },
    "gemma-2-26b": {
        "display_name": "Gemma 26B (fast)",
        "candidate_ids": [
            "gemma-4-26b-a4b-it",
            "gemma-2-26b-it",
            "gemma-2-27b-it",
        ],
        "cooldown_seconds": 5.0,
    },
    # Legacy option key kept for old UI/env; resolves to same fast 26B chain (not 31B).
    "gemma-4-31b": {
        "display_name": "Gemma 26B (fast)",
        "candidate_ids": ["gemma-4-26b-a4b-it", "gemma-2-26b-it", "gemma-2-27b-it"],
        "cooldown_seconds": 5.0,
    },
}

COOLDOWN_RULES = {
    candidate_id: config["cooldown_seconds"]
    for config in MODEL_OPTION_CONFIG.values()
    for candidate_id in config["candidate_ids"]
}

# Store last invocation timestamps globally
LAST_INVOCATION = {}
# Short-lived penalty for models that just timed out (were slow this cycle). Lets the
# next stage in the same turn skip a slow primary (e.g. Gemma) and go straight to the
# fast fallback, so the owner never waits through repeated slow calls in one turn.
SLOW_MODEL_PENALTY: dict[str, float] = {}
SLOW_MODEL_PENALTY_SECONDS = 45.0
VERIFIED_MODELS_CACHE = set()
LAST_MODEL_LIST_STATUS = {"status": "not_checked", "reason": ""}
LIVE_MODEL_LIST_STATUSES = {"success", "cache_hit", "config_fallback"}


def get_model_candidates(option: str) -> list[str]:
    config = MODEL_OPTION_CONFIG.get(option)
    if not config:
        return []
    return list(config["candidate_ids"])


def get_last_model_list_status() -> dict:
    return dict(LAST_MODEL_LIST_STATUS)


def is_model_list_live_verified() -> bool:
    return LAST_MODEL_LIST_STATUS.get("status") in LIVE_MODEL_LIST_STATUSES


def describe_model_verification(resolved_id: str | None, *, fallback: bool = False) -> str:
    if not resolved_id:
        return "fallback_not_verified" if fallback else "not_verified"
    if is_model_list_live_verified():
        return "verified_fallback" if fallback else "verified"
    if LAST_MODEL_LIST_STATUS.get("status") == "key_missing":
        return "key_missing"
    return "fallback_config_not_live_verified" if fallback else "config_fallback_not_live_verified"


def _safe_error_summary(exc: Exception) -> str:
    text = str(exc)
    if "WinError 10013" in text:
        return "network_blocked"
    if "Failed to establish a new connection" in text or "NewConnectionError" in text:
        return "connection_failed"
    if "timed out" in text.lower():
        return "timeout"
    return exc.__class__.__name__

def get_gemini_api_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if key and "your_" not in key.lower() and "placeholder" not in key.lower():
        return key
    # Fallback to config.json
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                return data.get("gemini_api_key", "")
        except Exception:
            pass
    return ""


def is_llm_configured() -> bool:
    """Used by the brain for local routing decisions without exposing keys."""
    if os.environ.get("LLM_PROVIDER_CHOICE") == "ollama":
        return True
    return bool(get_gemini_api_key())


def is_disallowed_normal_flow_model(api_id: str | None) -> bool:
    return is_disallowed_normal_flow(api_id)


def _filter_approved_models(model_ids: list[str]) -> list[str]:
    return [m for m in model_ids if not is_disallowed_normal_flow(m)]


def _config_fallback_models() -> list[str]:
    return _filter_approved_models(list(CONFIG_APPROVED_API_IDS))


def refresh_model_cache_from_api(api_key: str | None = None) -> dict:
    """
    Explicit network model discovery — startup, diagnostics, manual health only.
    """
    global VERIFIED_MODELS_CACHE
    key = api_key or get_gemini_api_key()
    if not key:
        LAST_MODEL_LIST_STATUS.update({"status": "key_missing", "reason": ""})
        return dict(LAST_MODEL_LIST_STATUS)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        res = requests.get(url, timeout=MODEL_LIST_NETWORK_TIMEOUT, verify=get_ssl_verify())
        if res.status_code == 200:
            models = res.json().get("models", [])
            available = []
            for m in models:
                name = m.get("name", "")
                if name.startswith("models/"):
                    available.append(name.replace("models/", ""))
            filtered = _filter_approved_models(available)
            if filtered:
                with _MODEL_CACHE_LOCK:
                    VERIFIED_MODELS_CACHE = set(filtered)
                LAST_MODEL_LIST_STATUS.update({"status": "success", "reason": ""})
                logger.info("Model cache refreshed (%d approved ids)", len(filtered))
                return dict(LAST_MODEL_LIST_STATUS)
            LAST_MODEL_LIST_STATUS.update({"status": "list_models_empty", "reason": ""})
        else:
            LAST_MODEL_LIST_STATUS.update(
                {"status": "list_models_http_error", "reason": f"http_{res.status_code}"}
            )
    except Exception as e:
        reason = _safe_error_summary(e)
        LAST_MODEL_LIST_STATUS.update({"status": "list_models_failed", "reason": reason})
        logger.warning("Model list refresh failed: %s", reason)
    return dict(LAST_MODEL_LIST_STATUS)


def warm_model_cache_background() -> None:
    """Non-blocking startup cache warm (does not block command hot path)."""

    def _run():
        try:
            refresh_model_cache_from_api()
        except Exception as exc:
            logger.warning("Background model cache warm failed: %s", exc)

    threading.Thread(target=_run, name="model-cache-warm", daemon=True).start()


def get_available_api_models(api_key: str, *, allow_network_refresh: bool = False) -> list[str]:
    """
    Hot path: cache or config fallback only.
    Network listModels only when allow_network_refresh=True.
    """
    global VERIFIED_MODELS_CACHE
    if VERIFIED_MODELS_CACHE:
        LAST_MODEL_LIST_STATUS.update({"status": "cache_hit", "reason": ""})
        return list(VERIFIED_MODELS_CACHE)

    if allow_network_refresh and api_key:
        refresh_model_cache_from_api(api_key)
        if VERIFIED_MODELS_CACHE:
            return list(VERIFIED_MODELS_CACHE)

    if not api_key:
        LAST_MODEL_LIST_STATUS.update({"status": "key_missing", "reason": ""})
    else:
        LAST_MODEL_LIST_STATUS.update({"status": "config_fallback", "reason": "cache_empty"})

    return _config_fallback_models()


def resolve_model_for_role(role: str) -> str | None:
    """Resolve approved API model id for a role using cache/config only."""
    if os.environ.get("LLM_PROVIDER_CHOICE") == "ollama":
        return os.environ.get("OLLAMA_MODEL_ID", "ollama/llama3")

    from services.llm.model_roles import resolve_role_to_api_id

    api_key = get_gemini_api_key()
    available = set(get_available_api_models(api_key, allow_network_refresh=False))
    return resolve_role_to_api_id(role, available)


def resolve_and_verify_model(
    option: str,
    api_key: str,
    *,
    allow_network_refresh: bool = False,
) -> str | None:
    """
    Resolves internal option to API model id.
    Hot path uses cache/config only unless allow_network_refresh=True.
    """
    available_models = get_available_api_models(
        api_key, allow_network_refresh=allow_network_refresh
    )
    config = MODEL_OPTION_CONFIG.get(option)
    if not config:
        return None
    for candidate in config["candidate_ids"]:
        if candidate in available_models and not is_disallowed_normal_flow(candidate):
            return candidate
    return None

def check_and_enforce_cooldown(
    model_id: str,
    *,
    max_wait_seconds: float | None = None,
) -> tuple[bool, float]:
    """
    Enforces per-model cooldown to avoid rate-limiting.
    - If wait <= max_wait (default SHORT_SAFE_DELAY): sleep and proceed.
    - If wait > max_wait: skip and return (False, wait_time).
    Pass max_wait_seconds=FALLBACK_COOLDOWN_WAIT_SECONDS for the last model in a
    dual-model chain so a ~3–8s cooldown does not kill the reply.
    """
    now = time.time()
    last = LAST_INVOCATION.get(model_id, 0.0)
    cooldown_needed = COOLDOWN_RULES.get(model_id, 4.0)
    elapsed = now - last
    max_wait = SHORT_SAFE_DELAY_SECONDS if max_wait_seconds is None else float(max_wait_seconds)

    if elapsed < cooldown_needed:
        wait_time = cooldown_needed - elapsed
        if wait_time <= max_wait:
            logger.info("Cooldown guard: sleeping %.2fs for model %s", wait_time, model_id)
            time.sleep(wait_time)
            return True, 0.0
        logger.warning(
            "Cooldown guard: skipping call for %s, requires %.2fs (max_wait=%.2fs)",
            model_id,
            wait_time,
            max_wait,
        )
        return False, wait_time

    return True, 0.0

def update_model_invocation_time(model_id: str):
    """Updates the invocation timestamp to the current time."""
    LAST_INVOCATION[model_id] = time.time()


def mark_model_slow(model_id: str, seconds: float = SLOW_MODEL_PENALTY_SECONDS):
    """Flag a model as slow (just timed out) for a short window."""
    if model_id:
        SLOW_MODEL_PENALTY[model_id] = time.time() + max(0.0, seconds)


def is_model_penalized(model_id: str) -> bool:
    """True while a model is inside its slow-timeout penalty window."""
    until = SLOW_MODEL_PENALTY.get(model_id, 0.0)
    if until <= 0.0:
        return False
    if time.time() >= until:
        SLOW_MODEL_PENALTY.pop(model_id, None)
        return False
    return True


def peek_cooldown_wait(model_id: str) -> float:
    """Return remaining cooldown seconds without sleeping (0 if ready)."""
    now = time.time()
    last = LAST_INVOCATION.get(model_id, 0.0)
    cooldown_needed = COOLDOWN_RULES.get(model_id, 4.0)
    elapsed = now - last
    if elapsed < cooldown_needed:
        return cooldown_needed - elapsed
    return 0.0


def get_retry_after_hint(wait_seconds: float | None = None) -> str:
    if wait_seconds and wait_seconds > 0:
        lo = max(15, int(wait_seconds))
        hi = min(60, lo + 15)
        return f"{lo}-{hi} second"
    return "20-30 second"


def build_owner_cooldown_reply(wait_seconds: float | None = None) -> str:
    hint = get_retry_after_hint(wait_seconds)
    return (
        f"Sir Gemini abhi cooldown me hai, {hint} baad dobara try kariye. "
        "Status/diagnostics commands abhi bhi chal sakte hain."
    )


# --- Shared generateContent choke-point (queue + gate + 429 backoff) ---

_MODEL_QUEUES: dict[str, threading.Condition] = {}
_MODEL_BUSY: dict[str, bool] = {}
_QUEUE_META_LOCK = threading.Lock()
_MAX_429_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.5
_BACKOFF_CAP_SECONDS = 12.0


def _queue_for(model_id: str) -> threading.Condition:
    with _QUEUE_META_LOCK:
        if model_id not in _MODEL_QUEUES:
            _MODEL_QUEUES[model_id] = threading.Condition(threading.Lock())
            _MODEL_BUSY[model_id] = False
        return _MODEL_QUEUES[model_id]


def _acquire_model_slot(model_id: str, *, priority: str, wait_budget: float = 30.0) -> bool:
    cond = _queue_for(model_id)
    deadline = time.time() + max(1.0, wait_budget)
    with cond:
        while _MODEL_BUSY.get(model_id):
            remaining = deadline - time.time()
            if remaining <= 0:
                return False
            cond.wait(timeout=min(remaining, 2.0))
        _MODEL_BUSY[model_id] = True
        return True


def _release_model_slot(model_id: str) -> None:
    cond = _queue_for(model_id)
    with cond:
        _MODEL_BUSY[model_id] = False
        cond.notify_all()


def _retry_after_seconds(response: requests.Response | None, attempt: int) -> float:
    if response is not None:
        ra = response.headers.get("Retry-After") or response.headers.get("retry-after")
        if ra:
            try:
                return min(_BACKOFF_CAP_SECONDS, max(0.5, float(ra)))
            except ValueError:
                pass
    delay = _BACKOFF_BASE_SECONDS * (2 ** attempt) + (0.1 * attempt)
    return min(_BACKOFF_CAP_SECONDS, delay)


def resolve_lite_api_id(api_key: str) -> str | None:
    available = set(get_available_api_models(api_key, allow_network_refresh=False))
    for cid in get_model_candidates("gemini-3.1-flash-lite"):
        if cid in available and not is_disallowed_normal_flow(cid):
            return cid
    for cid in ("gemini-3.1-flash-lite", "gemini-1.5-flash-8b", "gemini-1.5-flash"):
        if not is_disallowed_normal_flow(cid):
            return cid
    return None


def call_generate_content(
    model_id: str,
    api_key: str,
    payload: dict,
    *,
    timeout: float = 30.0,
    priority: str = "owner",
    purpose: str = "chat",
    wait_out_cooldown: bool = False,
) -> tuple[requests.Response | None, str, dict]:
    """Single choke-point for all text generateContent calls.

    Returns (response_or_None, status, meta).
    status: available | rate_limited | timeout | error | cooldown | quota_deferred | queue_timeout
    """
    import services.llm.quota_gatekeeper as gate

    mid = (model_id or "").strip()
    meta: dict = {"model_id": mid, "priority": priority, "purpose": purpose, "attempts": 0}
    if not mid:
        return None, "error", meta

    if mid.startswith("ollama/"):
        import os
        import requests
        contents = payload.get("contents", [])
        system_instruction = payload.get("systemInstruction") or payload.get("system_instruction")
        
        messages = []
        if system_instruction:
            parts = system_instruction.get("parts", [])
            sys_text = " ".join(p.get("text", "") for p in parts)
            if sys_text:
                messages.append({"role": "system", "content": sys_text})
                
        for content in contents:
            role = content.get("role", "user")
            if role == "model":
                role = "assistant"
            parts = content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts)
            messages.append({"role": role, "content": text})
            
        ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        url = f"{ollama_base}/api/chat"
        
        model_name = mid.split("/")[-1]
        ollama_payload = {
            "model": model_name,
            "messages": messages,
            "stream": False
        }
        
        logger.info("Ollama Request: model=%s, messages_count=%d", model_name, len(messages))
        try:
            res = requests.post(url, json=ollama_payload, timeout=timeout)
            if res.status_code == 200:
                ollama_reply = res.json().get("message", {}).get("content", "")
                mock_json = {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": ollama_reply
                                    }
                                ]
                            }
                        }
                    ]
                }
                
                class MockResponse:
                    def __init__(self, json_data, status_code):
                        self.json_data = json_data
                        self.status_code = status_code
                        self.headers = {}
                    def json(self):
                        return self.json_data
                
                logger.info("Ollama response successful: %s", ollama_reply[:150])
                meta["model_id"] = mid
                return MockResponse(mock_json, 200), "available", meta
            else:
                logger.error("Ollama returned status code: %d", res.status_code)
                return None, "error", meta
        except Exception as e:
            logger.error("Ollama execution failed: %s", e)
            return None, "error", meta

    if not api_key:
        return None, "error", meta

    decision = gate.evaluate_request(mid, priority=priority, purpose=purpose)  # type: ignore[arg-type]
    meta["gate"] = decision
    if not decision.get("allow"):
        return None, str(decision.get("status") or "quota_deferred"), meta

    use_id = mid
    if decision.get("force_lite") and purpose in (
        "conversation",
        "customer",
        "agent_step",
        "interpreter",
        "chat",
    ):
        lite = resolve_lite_api_id(api_key)
        if lite:
            use_id = lite
            meta["forced_lite"] = True
            meta["model_id"] = use_id

    max_wait = FALLBACK_COOLDOWN_WAIT_SECONDS if wait_out_cooldown else None
    can_proceed, wait_needed = check_and_enforce_cooldown(use_id, max_wait_seconds=max_wait)
    if not can_proceed:
        meta["cooldown_wait"] = wait_needed
        return None, "cooldown", meta

    if not _acquire_model_slot(use_id, priority=priority):
        return None, "queue_timeout", meta

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{use_id}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    last_status = "error"
    try:
        for attempt in range(_MAX_429_RETRIES + 1):
            meta["attempts"] = attempt + 1
            update_model_invocation_time(use_id)
            try:
                res = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    verify=get_ssl_verify(),
                )
            except requests.exceptions.Timeout:
                mark_model_slow(use_id)
                last_status = "timeout"
                break
            except Exception as exc:
                meta["error"] = _safe_error_summary(exc)
                last_status = "error"
                break

            if res.status_code == 429:
                last_status = "rate_limited"
                if attempt >= _MAX_429_RETRIES:
                    break
                time.sleep(_retry_after_seconds(res, attempt))
                continue
            if res.status_code >= 400:
                meta["http_status"] = res.status_code
                last_status = "error"
                break

            gate.record_success(use_id)
            meta["model_id"] = use_id
            return res, "available", meta

        return None, last_status, meta
    finally:
        _release_model_slot(use_id)


def call_generate_content_json(
    model_id: str,
    api_key: str,
    payload: dict,
    *,
    timeout: float = 30.0,
    priority: str = "owner",
    purpose: str = "chat",
    wait_out_cooldown: bool = False,
) -> tuple[dict | None, str, dict]:
    res, status, meta = call_generate_content(
        model_id,
        api_key,
        payload,
        timeout=timeout,
        priority=priority,
        purpose=purpose,
        wait_out_cooldown=wait_out_cooldown,
    )
    if status != "available" or res is None:
        return None, status, meta
    try:
        return res.json(), status, meta
    except Exception:
        return None, "error", meta


def is_model_rate_limited_status(status: str) -> bool:
    return status in ("cooldown", "rate_limited")


def apply_model_limit_trace(tb, *, model_call_status: str, wait_seconds: float = 0.0) -> None:
    if tb is None:
        return
    tb.model_call_status = model_call_status
    tb.model_rate_limited = is_model_rate_limited_status(model_call_status)
    tb.retry_after_hint = get_retry_after_hint(wait_seconds) if tb.model_rate_limited else None


def query_llm(model_option: str, system_prompt: str, user_message: str, max_output_tokens: int = 1200) -> tuple[str, str, str, str | None]:
    """
    Main LLM call wrapper with mapping, verification, cooldown, and error handling.
    Returns a tuple: (reply_text, provider, status_string, resolved_api_model_id)
    
    Status strings: available | model_unavailable | unavailable | rate_limited | timeout | error | cooldown
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return "__LLM_UNAVAILABLE__:no_key", "none", "unavailable", None
        
    # 1. Resolve model ID from cache/config (no network on hot path)
    resolved_id = resolve_and_verify_model(model_option, api_key, allow_network_refresh=False)
    if not resolved_id:
        logger.error(f"Model ID verification failed for option {model_option}")
        return f"Selected model unavailable: {model_option}. Verified API model mapping nahi mili.", "none", "model_unavailable", None
        
    provider = "gemma" if "gemma" in resolved_id else "gemini"
    
    # History + tools; cooldown/queue/429 handled inside call_generate_content
    contents = memory_adapter.load_chat_history_contents(limit=10)
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })
    
    tools = tr.get_tools_definition()
    
    # 5-turn function call loop
    for turn in range(5):
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "tools": tools,
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": max_output_tokens
            }
        }
        
        try:
            res, http_status, meta = call_generate_content(
                resolved_id,
                api_key,
                payload,
                timeout=30.0,
                priority="owner",
                purpose="chat",
            )
            if http_status == "cooldown":
                return build_owner_cooldown_reply(meta.get("cooldown_wait")), provider, "cooldown", resolved_id
            if http_status == "quota_deferred":
                from services.llm.quota_gatekeeper import build_quota_defer_reply

                return build_quota_defer_reply(role="owner"), provider, "quota_deferred", resolved_id
            if http_status == "rate_limited":
                logger.error(f"API Rate Limited (429) for model {resolved_id}")
                return "__LLM_UNAVAILABLE__:rate_limited", provider, "rate_limited", resolved_id
            if http_status != "available" or res is None:
                logger.error(f"API Error ({http_status}) for model {resolved_id}")
                return f"__LLM_UNAVAILABLE__:{http_status}", provider, http_status if http_status in ("timeout", "error") else "provider_error", resolved_id

            resolved_id = meta.get("model_id") or resolved_id
            provider = "gemma" if "gemma" in resolved_id else "gemini"
            res_json = res.json()
            candidate = res_json["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            function_call = None
            text_response = ""
            
            for part in parts:
                if "functionCall" in part:
                    function_call = part["functionCall"]
                if "text" in part:
                    text_response += part["text"]
            
            if function_call:
                name = function_call["name"]
                args = function_call.get("args", {})
                
                # Enforce safety guard policy checks
                guard_res = policy_guard.check_permission(actor_role="owner", action_name=name)
                if not guard_res["allowed"]:
                    logger.warning(f"Policy Guard blocked action '{name}': {guard_res['message']}")
                    tool_result = {"success": False, "error": guard_res["message"]}
                else:
                    logger.info(f"Dispatching tool call '{name}' with args {args}")
                    tool_result = tr.dispatch_tool_call(name, args)
                
                contents.append(content)
                contents.append({
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": name,
                                "response": {
                                    "name": name,
                                    "content": tool_result
                                }
                            }
                        }
                    ]
                })
                # Proceed to next turn of loop
                continue
            else:
                return text_response.strip(), provider, "available", resolved_id
                
        except Exception as e:
            reason = _safe_error_summary(e)
            logger.error(f"Request exception for model {resolved_id}: {reason}")
            return f"__LLM_UNAVAILABLE__:provider_error:{reason}", provider, "provider_error", resolved_id
            
    return "__LLM_UNAVAILABLE__:max_turns", provider, "provider_error", resolved_id

import os
import json
import logging
import time
import requests
from fastapi import FastAPI, HTTPException, Request, Body, BackgroundTasks, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import sys
sys.path.append(os.path.dirname(__file__))

import database as db
import services.cockpit.runtime_controller as rc
from services.cockpit.recorder import record_whatsapp_turn
from services.safety.admin_security import CommandCenterSecurityMiddleware, HealthProbeMiddleware, security_status
from services.safety.admin_unlock import (
    SESSION_COOKIE_NAME,
    cookie_secure_flag,
    create_session_token,
    session_cookie_max_age,
    unlock_phrase_configured,
    verify_unlock_phrase,
)
import asyncio
from services.cockpit.resource_monitor import start_monitoring_loop
from services.cockpit.runtime_controller import get_whatsapp_gateway_url
from services.safety.security_config import get_ssl_verify

# Load environment variables manually
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts[0].strip(), parts[1].strip()
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"):
                            val = val[1:-1]
                        if key not in os.environ:
                            os.environ[key] = val

load_env()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
db.init_db()

from app_core import limiter
app = FastAPI(title="AI Radio Station Manager API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rule 6: every HTTPException is upgraded to the standard structured error
# envelope (error_code/recoverable/next_action) while keeping `detail` for
# backward-compatible frontend parsing. Registered for the Starlette base so it
# covers FastAPI HTTPException and NeenaHTTPError alike.
from starlette.exceptions import HTTPException as _StarletteHTTPException
from services.brain.error_handler import neena_http_exception_handler
app.add_exception_handler(_StarletteHTTPException, neena_http_exception_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CommandCenterSecurityMiddleware)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Outermost — liveness must stay fast even when chat/launch-health saturate workers.
app.add_middleware(HealthProbeMiddleware)

# Feature-wise routers (rule 2/4: one HTTP domain per module).
from routers import broadcast as broadcast_router
from routers import public as public_router
from routers import neena_agent_ux as neena_agent_ux_router
from routers import azuracast_webhook as azuracast_webhook_router
app.include_router(broadcast_router.router)
app.include_router(public_router.router)
app.include_router(neena_agent_ux_router.router)
app.include_router(azuracast_webhook_router.router)

# Load configuration / API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def get_api_keys():
    global GEMINI_API_KEY, ELEVENLABS_API_KEY
    g_key = GEMINI_API_KEY
    el_key = ELEVENLABS_API_KEY
    
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                if not g_key:
                    g_key = data.get("gemini_api_key", "")
                if not el_key:
                    el_key = data.get("elevenlabs_api_key", "")
        except Exception:
            pass
    return g_key, el_key

def save_api_keys(g_key: str, el_key: str):
    global GEMINI_API_KEY, ELEVENLABS_API_KEY
    GEMINI_API_KEY = g_key
    ELEVENLABS_API_KEY = el_key
    with open(CONFIG_PATH, "w") as f:
        json.dump({"gemini_api_key": g_key, "elevenlabs_api_key": el_key}, f)

# Global WhatsApp Gateway state
whatsapp_state = {
    "status": "disconnected",  # 'disconnected', 'connecting', 'qr_ready', 'connected'
    "qr_code_data": "",
    "phone": ""
}

# --- Pydantic Schemas ---
class APIKeysUpdate(BaseModel):
    gemini_key: str
    elevenlabs_key: Optional[str] = ""

class CommandRequest(BaseModel):
    command_type: str
    payload_json: Optional[str] = None

class OwnerChatRequest(BaseModel):
    message: str
    model: Optional[str] = "auto"

class CockpitActionRequest(BaseModel):
    action: str
    watch_seconds: Optional[int] = 30


class LiveOpsQuickRequest(BaseModel):
    message: str = ""
    action: str = ""


class AdminUnlockRequest(BaseModel):
    phrase: str

# Startup event to launch system resource monitor background daemon
@app.on_event("startup")
async def startup_event():
    from services.llm.provider_router import warm_model_cache_background

    warm_model_cache_background()
    asyncio.create_task(start_monitoring_loop())
    try:
        from services.cockpit.deferred_status import start_deferred_status_loop

        asyncio.create_task(start_deferred_status_loop())
    except Exception:
        pass
    def _memory_boot():
        from services.memory.pg_repository import ensure_postgres_memory_schema
        from services.brain.self_knowledge import seed_self_knowledge
        ensure_postgres_memory_schema()
        try:
            seed_self_knowledge(with_embeddings=True)
        except Exception:
            pass
        try:
            from services.memory.self_change import reconcile_on_boot
            reconcile_on_boot()
        except Exception:
            pass
        try:
            from services.cockpit.self_heal import announce_pending_on_boot
            announce_pending_on_boot()
        except Exception:
            pass
    asyncio.get_event_loop().run_in_executor(None, _memory_boot)

@app.get("/api/config/status")
def check_config():
    g_key, el_key = get_api_keys()
    public_url = os.environ.get("PUBLIC_BASE_URL", "")
    is_missing = lambda val: not val or "here" in val.lower() or "your_" in val.lower() or "placeholder" in val.lower()
    
    fallback_verified = False
    if not is_missing(g_key):
        try:
            from services.llm.provider_router import resolve_and_verify_model
            fallback_verified = resolve_and_verify_model(
                "gemma-4-31b", g_key, allow_network_refresh=True
            ) is not None
        except Exception:
            pass
            
    return {
        "gemini_api_key_configured": not is_missing(g_key),
        "elevenlabs_api_key_configured": not is_missing(el_key),
        "public_base_url_configured": not is_missing(public_url),
        "public_base_url": public_url,
        "fallback_model_verified": fallback_verified
    }

@app.post("/api/config/key")
def update_keys(data: APIKeysUpdate):
    if not data.gemini_key.strip():
        raise HTTPException(status_code=400, detail="Gemini key cannot be empty")
    
    save_api_keys(data.gemini_key.strip(), data.elevenlabs_key.strip() if data.elevenlabs_key else "")
    
    # Also write to .env if writable
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            keys_updated = {"GEMINI_API_KEY": False, "ELEVENLABS_API_KEY": False}
            for i, line in enumerate(lines):
                if line.strip().startswith("GEMINI_API_KEY="):
                    lines[i] = f"GEMINI_API_KEY={data.gemini_key.strip()}\n"
                    keys_updated["GEMINI_API_KEY"] = True
                elif line.strip().startswith("ELEVENLABS_API_KEY="):
                    lines[i] = f"ELEVENLABS_API_KEY={data.elevenlabs_key.strip()}\n"
                    keys_updated["ELEVENLABS_API_KEY"] = True
            
            if not keys_updated["GEMINI_API_KEY"]:
                lines.append(f"GEMINI_API_KEY={data.gemini_key.strip()}\n")
            if not keys_updated["ELEVENLABS_API_KEY"]:
                lines.append(f"ELEVENLABS_API_KEY={data.elevenlabs_key.strip()}\n")
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass
            
    return {"status": "success", "message": "API keys saved successfully"}

@app.get("/api/whatsapp/status")
def get_whatsapp_status():
    global whatsapp_state
    gateway_running = False
    try:
        res = requests.get(get_whatsapp_gateway_url("status"), timeout=1.0, verify=get_ssl_verify())
        if res.status_code == 200:
            data = res.json()
            whatsapp_state.update(data)
            db.update_service_status("whatsapp_gateway", "Live" if data.get("status") == "connected" else "Offline")
            gateway_running = True
    except Exception:
        whatsapp_state["status"] = "disconnected"
        db.update_service_status("whatsapp_gateway", "Offline")
        gateway_running = False
        
    res_data = dict(whatsapp_state)
    res_data["gateway_running"] = gateway_running
    return res_data

@app.post("/api/whatsapp/status")
def update_whatsapp_status(data: dict = Body(...)):
    global whatsapp_state
    whatsapp_state.update(data)
    db.update_service_status("whatsapp_gateway", "Live" if data.get("status") == "connected" else "Offline")
    return {"status": "success"}

@app.post("/api/whatsapp/webhook")
def whatsapp_webhook(data: dict = Body(...)):
    """
    Called by Node.js WhatsApp gateway. Processes texts and voice notes.
    """
    phone = data.get("phone", "")
    message = data.get("message", "")
    media_url = data.get("media_url", "")
    
    if not phone:
        raise HTTPException(status_code=400, detail="Missing phone")
        
    if media_url:
        started = time.monotonic()
        try:
            from services.voice.whatsapp_handler import handle_incoming_voice_note

            filepath = handle_incoming_voice_note(media_url, phone)
            reply = "Dhanyavaad Sir! Aapka voice note broadcast schedule ke liye download kar liya gaya hai."
            media_file = os.path.basename(filepath)
            owner_raw = os.environ.get("OWNER_WHATSAPP_NUMBER", "+918787029878")
            owner_digits = "".join(c for c in owner_raw if c.isdigit())
            phone_digits = "".join(c for c in phone if c.isdigit())
            is_owner = bool(phone_digits and owner_digits and (
                phone_digits == owner_digits or phone_digits[-10:] == owner_digits[-10:]
            ))
            if not is_owner and data.get("is_owner") is True:
                is_owner = True
            record_whatsapp_turn(
                user_input=message or "[voice_note]",
                result={
                    "reply": reply,
                    "action_type": "WHATSAPP_VOICE_NOTE",
                    "route": "whatsapp_voice",
                    "media_kind": "voice_note",
                    "media_file": media_file,
                    "ok": True,
                },
                latency_ms=round((time.monotonic() - started) * 1000),
                is_owner=is_owner,
            )
            return {
                "reply": reply,
                "media_file": media_file,
            }
        except Exception as e:
            logger.error(f"Error executing WhatsApp voice handler: {e}")
            try:
                # Nested import would shadow module-level name → UnboundLocalError on text path.
                record_whatsapp_turn(
                    user_input=message or "[voice_note]",
                    result={
                        "reply": "Voice note handle nahi ho paya.",
                        "action_type": "WHATSAPP_VOICE_NOTE_FAILED",
                        "route": "whatsapp_voice",
                        "media_kind": "voice_note",
                        "ok": False,
                        "success": False,
                        "block_reason": type(e).__name__,
                    },
                    latency_ms=round((time.monotonic() - started) * 1000),
                    is_owner=True,
                )
            except Exception:
                pass

    if not message:
        raise HTTPException(status_code=400, detail="Missing message")
        
    owner_raw = os.environ.get("OWNER_WHATSAPP_NUMBER", "+918787029878")
    owner_digits = "".join(c for c in owner_raw if c.isdigit())
    phone_digits = "".join(c for c in phone if c.isdigit())

    # Robust owner match: last 10 digits (national number) or exact, so country-code
    # / formatting differences don't misroute the owner as a customer.
    is_owner = bool(phone_digits and owner_digits and (
        phone_digits == owner_digits or phone_digits[-10:] == owner_digits[-10:]
    ))
    # The local gateway already resolves the real sender (handling WhatsApp LID
    # ids that don't match the phone number) and passes an explicit hint. This
    # endpoint is local-only, so trust the hint when the number check can't confirm.
    if not is_owner and data.get("is_owner") is True:
        is_owner = True
    if is_owner:
        from services.brain.always_reply import safe_owner_result
        from services.brain.message_router import process_message
        started = time.monotonic()
        try:
            res = process_message(role="owner", message=message, channel="whatsapp")
        except Exception as exc:
            logger.error("WhatsApp owner chat failed: %s", exc)
            res = safe_owner_result(message, error=exc)
        reply_text = res.get("reply") or safe_owner_result(message)["reply"]
        record_whatsapp_turn(user_input=message, result=res, latency_ms=round((time.monotonic() - started) * 1000), is_owner=True)
        db.add_activity_log("chat", f"WhatsApp Owner: '{message}'")
        db.add_activity_log("chat", f"Neena replied (WhatsApp): '{reply_text[:60]}...'")
        return {"reply": reply_text}
    from services.brain.message_router import process_message
    started = time.monotonic()
    result = process_message(
        role="customer",
        message=message,
        sender_name=data.get("sender_name") or "ji",
        phone=phone,
    )
    reply_text = (result.get("reply") or "").strip()
    record_whatsapp_turn(user_input=message, result=result, latency_ms=round((time.monotonic() - started) * 1000), is_owner=False)
    return {"reply": reply_text}

@app.post("/api/neena/chat")
def chat_with_neena(request: Request, data: OwnerChatRequest):
    """Owner interactive console — always returns a non-empty reply dict."""
    from services.cockpit.recorder import apply_session_cookie, record_chat_turn
    from services.brain.always_reply import safe_owner_result
    db.add_activity_log("command", f"Owner console message: '{data.message}' (model: {data.model})")
    started = time.monotonic()
    try:
        from services.brain.message_router import process_message

        res = process_message(role="owner", message=data.message, selected_model=data.model)
        if not isinstance(res, dict) or not (res.get("reply") or "").strip():
            res = safe_owner_result(data.message, reply=(res or {}).get("reply") if isinstance(res, dict) else None)
    except Exception as exc:
        logger.error("Owner chat failed: %s", exc)
        res = safe_owner_result(data.message, error=exc)
    latency_ms = round((time.monotonic() - started) * 1000)
    res.setdefault("mode", os.environ.get("RUNTIME_MODE", "LOCAL_TEST_MODE"))
    _, session_id, is_new_session = record_chat_turn(
        request=request, user_input=data.message, result=res, selected_model=data.model, latency_ms=latency_ms,
    )
    if is_new_session and session_id:
        response = JSONResponse(content=res)
        apply_session_cookie(response, session_id)
        return response
    return res

@app.post("/api/neena/cockpit-action")
def post_neena_cockpit_action(request: Request, data: CockpitActionRequest):
    """M4-A8.2-A / M4-A8.3 — fast immediate or background cockpit actions (no Gemini)."""
    from services.cockpit.action_service import COCKPIT_ACTIONS, dispatch_cockpit_action
    from services.cockpit.recorder import record_cockpit_action_turn
    from services.llm.model_roles import get_public_role_map

    action = (data.action or "").strip().lower()
    if action not in COCKPIT_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
    started = time.monotonic()
    result = dispatch_cockpit_action(action, watch_seconds=int(data.watch_seconds or 30))
    result["model_role_map"] = get_public_role_map()
    record_cockpit_action_turn(
        request=request,
        action=action,
        result=result,
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    return result

@app.get("/api/neena/cockpit-jobs/{job_id}")
def get_neena_cockpit_job(job_id: str):
    """Poll background cockpit job status (SQLite-backed, cross-worker safe)."""
    from services.cockpit.job_service import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/neena/pending-completions")
def get_neena_pending_completions():
    """Drain finished background-job results not yet shown to the owner.

    Lets the web console deliver results even after a reload / poll timeout
    (server-side follow-through). Returned jobs are marked as seen.
    """
    from services.cockpit.job_service import list_unseen_finished_jobs, mark_owner_seen
    from services.cockpit.recorder import record_job_completion_turns
    import services.brain.feature_flags as feature_flags

    if not feature_flags.job_followup_enabled():
        return {"ok": True, "completions": []}

    jobs = list_unseen_finished_jobs(limit=10)
    if jobs:
        record_job_completion_turns(jobs)
        mark_owner_seen([j["job_id"] for j in jobs])
    return {"ok": True, "completions": jobs}

@app.get("/api/neena/model-roles")
def get_neena_model_roles():
    """Read-only approved model role map (no secrets)."""
    from services.llm.model_roles import get_public_role_map
    from services.llm.provider_router import get_last_model_list_status

    return {
        "status": "success",
        "roles": get_public_role_map(),
        "model_list_cache": get_last_model_list_status(),
    }

@app.get("/api/neena/launch-health")
def get_neena_launch_health():
    """Deep diagnostic health — cached, bounded timeouts (no secrets)."""
    from services.cockpit.launch_health import get_deep_launch_health

    return get_deep_launch_health()

@app.get("/api/neena/security-status")
def get_neena_security_status(request: Request):
    """Read-only Command Center exposure mode (no secrets)."""
    return {"status": "success", "security": security_status(request)}

@app.post("/api/admin/unlock")
@limiter.limit("10/minute")
def admin_unlock_phrase(request: Request, data: AdminUnlockRequest):
    """Owner phrase unlock — sets HttpOnly session cookie; phrase never logged."""
    from services.cockpit.recorder import (
        CC_SESSION_COOKIE,
        apply_session_cookie,
        end_session,
        record_admin_event,
        start_session,
    )

    if not unlock_phrase_configured():
        record_admin_event(
            event="unlock_not_configured",
            result={"detail": "Owner unlock phrase is not configured.", "ok": False},
            blocked=True,
            outcome="blocked",
        )
        raise HTTPException(status_code=503, detail="Owner unlock phrase is not configured.")
    accepted, _score = verify_unlock_phrase(data.phrase)
    if not accepted:
        record_admin_event(
            event="unlock_rejected",
            result={"detail": "Unlock phrase rejected.", "ok": False},
            blocked=True,
            outcome="blocked",
        )
        raise HTTPException(status_code=401, detail="Unlock phrase rejected.")
    try:
        token = create_session_token()
    except RuntimeError:
        record_admin_event(
            event="unlock_session_unconfigured",
            result={"detail": "Admin session is not configured.", "ok": False},
            blocked=True,
            outcome="blocked",
        )
        raise HTTPException(status_code=503, detail="Admin session is not configured.")

    prior_session = (request.cookies.get(CC_SESSION_COOKIE) or "").strip()
    if prior_session:
        end_session(prior_session, end_reason="re_unlock")
    session_id = start_session()
    record_admin_event(
        event="unlock_ok",
        result={"detail": "unlocked", "ok": True, "reply": "Command Center unlocked."},
        session_id=session_id,
        outcome="success",
    )
    response = JSONResponse(content={"status": "success", "unlocked": True, "session_id": session_id})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=session_cookie_max_age(),
        httponly=True,
        secure=cookie_secure_flag(),
        samesite="lax",
        path="/",
    )
    apply_session_cookie(response, session_id)
    return response


@app.post("/api/admin/lock")
def admin_lock_session(request: Request):
    """Clear owner session cookie."""
    from services.cockpit.recorder import CC_SESSION_COOKIE, clear_session_cookie, end_session, record_admin_event

    session_id = (request.cookies.get(CC_SESSION_COOKIE) or "").strip()
    end_session(session_id, end_reason="lock")
    record_admin_event(
        event="lock",
        result={"detail": "locked", "ok": True, "reply": "Command Center locked."},
        session_id=session_id or None,
        outcome="success",
    )
    response = JSONResponse(content={"status": "success", "unlocked": False})
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    clear_session_cookie(response)
    return response

@app.get("/api/neena/cockpit-status")
def get_neena_cockpit_status():
    """M4-A5R/M4-A7/M4-A8.3 — cache-only UI health poll (no blocking probes)."""
    from services.cockpit.status_fast import get_cockpit_status_ui_snapshot

    return get_cockpit_status_ui_snapshot()


@app.get("/api/neena/live-state")
def get_neena_live_state(deep: bool = False):
    """M4-A8.4 — NEENA_LIVE_STATE_SNAPSHOT for live operator awareness."""
    from services.brain.live_state_snapshot import build_neena_live_state_snapshot

    return {
        "status": "success",
        "live_state": build_neena_live_state_snapshot(include_deep_health=deep),
    }


@app.get("/api/neena/action-registry")
def get_neena_action_registry():
    """M4-A8.4 — COMMAND_CENTER_ACTION_REGISTRY with live enabled/blocked state."""
    from services.cockpit.action_registry import registry_to_public_map
    from services.brain.live_state_snapshot import build_neena_live_state_snapshot

    snap = build_neena_live_state_snapshot()
    reg = snap.get("action_registry") or []
    return {"status": "success", **registry_to_public_map(reg)}


@app.get("/api/neena/model-status")
def get_neena_model_status_endpoint():
    """M4-A8.5 — Owner-safe model runtime status (no secrets)."""
    from services.llm.model_status import build_neena_model_status

    return {"status": "success", **build_neena_model_status()}


@app.get("/api/neena/memory-status")
def get_neena_memory_status_endpoint():
    """M4-A8.5 — Owner-safe memory stack status (no secrets)."""
    from services.memory.status import build_neena_memory_status

    return {"status": "success", **build_neena_memory_status()}


@app.post("/api/neena/live-ops/quick")
def post_neena_live_ops_quick(request: Request, data: LiveOpsQuickRequest):
    """M4-A8.4.1 — Local live-state ops without Gemini (no hang for what_now/status/etc.)."""
    from services.cockpit.recorder import apply_session_cookie, record_live_ops_turn
    from services.tools.live_ops_quick import try_live_ops_quick

    started = time.monotonic()
    result = try_live_ops_quick(message=(data.message or "").strip(), action=(data.action or "").strip())
    latency_ms = round((time.monotonic() - started) * 1000)
    if not result:
        return {"handled": False, "status": "not_local_fast_action"}
    result["status"] = "success"
    _, session_id, is_new_session = record_live_ops_turn(
        request=request,
        user_input=(data.message or "").strip(),
        action=(data.action or "").strip(),
        result=result,
        latency_ms=latency_ms,
    )
    if is_new_session and session_id:
        response = JSONResponse(content=result)
        apply_session_cookie(response, session_id)
        return response
    return result


@app.get("/api/neena/interaction-records/recent")
def get_recent_interaction_records(
    session_limit: int = 10,
    turn_limit: int = 40,
    channel: str | None = None,
    session_id: str | None = None,
):
    """Read-only Command Center interaction history for agent analysis (no secrets)."""
    from services.cockpit.recorder import build_recent_interaction_bundle

    return build_recent_interaction_bundle(
        session_limit=session_limit,
        turn_limit=turn_limit,
        channel=(channel or "").strip() or None,
        session_id=(session_id or "").strip() or None,
    )


class CockpitVoiceSpeakRequest(BaseModel):
    text: str
    voice: str = "default"
    purpose: str = "owner_cockpit"
    priority: str = "progress"


@app.get("/api/neena/cockpit-voice/status")
def get_cockpit_voice_status_endpoint():
    """M4-A8.4.2 — Owner cockpit voice fallback provider status (no secrets)."""
    from services.voice.cockpit_voice import get_cockpit_voice_status

    return {"status": "success", **get_cockpit_voice_status()}


@app.post("/api/neena/cockpit-voice/speak")
def post_cockpit_voice_speak(request: Request, data: CockpitVoiceSpeakRequest):
    """M4-A8.4.3 — Queue owner-cockpit voice (returns job_id immediately)."""
    from services.cockpit.recorder import record_voice_turn
    from services.voice.cockpit_voice import DEFAULT_VOICE, enqueue_cockpit_voice

    voice = DEFAULT_VOICE if (data.voice or "default") == "default" else data.voice
    started = time.monotonic()
    result = enqueue_cockpit_voice(
        data.text,
        voice=voice,
        purpose=data.purpose or "owner_cockpit",
        priority=(data.priority or "progress").strip().lower(),
    )
    record_voice_turn(
        request=request,
        text=data.text or "",
        result=dict(result) if isinstance(result, dict) else {"reply": str(result)},
        latency_ms=round((time.monotonic() - started) * 1000),
        event_kind="speak",
    )
    return result


@app.get("/api/neena/cockpit-voice/jobs/{voice_job_id}")
def get_cockpit_voice_job(voice_job_id: str):
    """M4-A8.4.3 — Poll async cockpit voice job status."""
    from services.voice.cockpit_voice import get_voice_job_status

    return get_voice_job_status(voice_job_id)


@app.get("/api/neena/cockpit-voice/audio/{file_id}")
def get_cockpit_voice_audio(file_id: str):
    """Serve cached cockpit voice MP3/WAV."""
    from services.voice.cockpit_voice import resolve_audio_path

    path = resolve_audio_path(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="Audio not found")
    media_type = "audio/wav" if str(path).endswith(".wav") else "audio/mpeg"
    filename = os.path.basename(path)
    return FileResponse(str(path), media_type=media_type, filename=filename)


@app.get("/api/neena/dedications")
def get_neena_dedications():
    """Endpoint for admin dashboard to retrieve pending song dedications"""
    return db.get_pending_dedications(limit=10)

@app.get("/api/admin/approval-queue")
def get_admin_approval_queue():
    """Endpoint for admin dashboard to list assets pending manual review"""
    return db.get_pending_approvals(limit=15)

class ApprovalActionRequest(BaseModel):
    action: str  # approve | reject | dismiss | delete

@app.post("/api/admin/approval-queue/{approval_id}/action")
def post_approval_action(approval_id: int, data: ApprovalActionRequest):
    """Endpoint for admin dashboard to approve or reject a queued asset"""
    from services.broadcast.approval_queue import process_approval_action
    from services.cockpit.recorder import record_broadcast_turn

    started = time.monotonic()
    res = process_approval_action(approval_id, data.action)
    record_broadcast_turn(
        action=f"approval_queue_{data.action}",
        capsule_id=None,
        result={
            **(res if isinstance(res, dict) else {"reply": str(res)}),
            "approval_id": approval_id,
            "ui_action": data.action,
        },
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/admin/broadcast-capsules/{capsule_id}/archive")
def archive_broadcast_capsule(capsule_id: int):
    """Lab manual delete — soft-archive capsule (hidden from Lab lists)."""
    from services.broadcast.capsule_service import archive_capsule
    from services.cockpit.recorder import record_broadcast_turn

    started = time.monotonic()
    res = archive_capsule(capsule_id)
    record_broadcast_turn(
        action="capsule_archive",
        capsule_id=capsule_id,
        result=res if isinstance(res, dict) else {"reply": str(res)},
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message") or "Not found")
    return res


@app.post("/api/admin/approval-queue/{approval_id}/voice-preview")
def generate_voice_preview(approval_id: int):
    """
    Endpoint for admin dashboard to generate voice preview for an approved script.
    """
    # 1. Fetch item from approval queue
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Approval item ID {approval_id} not found.")
        
    item = dict(row)
    if item.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Voice preview can only be generated for approved scripts.")
        
    # 2. Get active voice persona
    voice_id = "21m00Tcm4TlvDq8ikWAM" # default Neena voice
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT elevenlabs_voice_id FROM voice_personas WHERE id = 'rj_neena' AND active = 1")
        v_row = cursor.fetchone()
        conn.close()
        if v_row and v_row["elevenlabs_voice_id"]:
            voice_id = v_row["elevenlabs_voice_id"]
    except Exception:
        pass
        
    # 3. Call voice generation service
    from services.voice.gen_service import render_approved_script
    try:
        render_result = render_approved_script(
            script_id=approval_id,
            voice_id=voice_id,
            text=item.get("content_data", "")
        )
        filepath = render_result.get("audio_file_path", "")
        filename = os.path.basename(filepath) if filepath and os.path.exists(filepath) else None
        response_status = "success" if render_result.get("status") == "preview_real" else render_result.get("truth_level", "unavailable")
        return {
            "status": response_status,
            "preview_status": render_result.get("status", "unavailable"),
            "truth_level": render_result.get("truth_level", "unknown"),
            "preview_type": "preview",
            "production_asset": False,
            "message": render_result.get("message", "Voice preview action completed."),
            "audio_file": filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")

@app.get("/api/runtime/status")
def get_runtime_status():
    """Telemetry snapshot — cache/DB only; no heartbeat probes on poll (M4-A8.3)."""
    status_list = db.get_station_runtime_status()
    commands = db.get_last_station_commands()

    services_state = {}
    for item in status_list:
        services_state[item["service_name"]] = {
            "status": item["status"],
            "last_heartbeat": item["last_heartbeat"],
            "details": json.loads(item["details_json"]) if item["details_json"] else {}
        }

    auto_mode = services_state.get("auto_mode", {}).get("status", "OFF")
    radio_stream = services_state.get("radio_stream", {}).get("status", "DISCONNECTED")
    wa_peek = rc.peek_whatsapp_gateway_trace_status()
    whatsapp_gateway = "Live" if wa_peek == "live" else ("Offline" if wa_peek == "offline" else "Unknown")
    
    uptime = rc.get_uptime()
    system_stats = rc.get_system_stats()
    
    runtime_mode = os.environ.get("RUNTIME_MODE", "")
    is_vm = "vm" in runtime_mode.lower() and sys.platform != "win32"
    env_mode = "VM_LIVE_MODE" if is_vm else "LOCAL_TEST_MODE"
    
    import urllib.parse
    public_url = os.environ.get("PUBLIC_BASE_URL", "http://35.244.15.150")
    try:
        public_ip = urllib.parse.urlparse(public_url).netloc.split(":")[0] or public_url.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
    except Exception:
        public_ip = "35.244.15.150"
    
    return {
        "services": services_state,
        "auto_mode": auto_mode,
        "radio_stream": radio_stream,
        "whatsapp_gateway": whatsapp_gateway,
        "uptime": uptime,
        "stats": system_stats,
        "mode": env_mode,
        "public_ip": public_ip,
        "commands": commands
    }

@app.post("/api/runtime/command")
def post_runtime_command(data: CommandRequest, background_tasks: BackgroundTasks):
    command_id = db.add_station_command(data.command_type, data.payload_json)
    background_tasks.add_task(rc.execute_station_command, command_id, data.command_type, data.payload_json)
    return {
        "status": "queued",
        "command_id": command_id,
        "message": f"Command '{data.command_type}' queued for execution."
    }

# --- Neena Lab Visibility v1 (Stage 2) ---

@app.get("/api/neena/lab")
def get_neena_lab():
    """
    Returns Neena Lab workspace state using existing database tables.
    Shows current task, script drafts, approval queue, voice assets,
    schedule, playout readiness, source tool readiness, and recent activity.
    Does not invent data — returns empty arrays if real data is empty.
    """
    import sys
    runtime_mode = os.environ.get("RUNTIME_MODE", "")
    is_vm = "vm" in runtime_mode.lower() and sys.platform != "win32"
    mode = "VM_LIVE_MODE" if is_vm else "LOCAL_TEST_MODE"

    # Current task — Neena is idle unless something is actively being processed
    current_task = {
        "status": "idle",
        "title": None
    }

    # Script drafts from approval queue (pending_review items)
    script_drafts = []
    try:
        pending = db.get_pending_approvals(limit=20)
        for item in pending:
            script_drafts.append({
                "id": item["id"],
                "type": item["asset_type"],
                "content_preview": (item.get("content_data", "") or "")[:120],
                "content_data": item.get("content_data", "") or "",
                "status": item["status"],
                "created_at": item.get("created_at", "")
            })
    except Exception:
        pass

    # Approval queue — same as script_drafts but all pending
    approval_queue = script_drafts  # They are the same source table for now

    # Voice/audio assets
    voice_assets = []
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM voice_assets ORDER BY id DESC LIMIT 20")
        for row in cursor.fetchall():
            item = dict(row)
            status = str(item.get("status", "unknown"))
            item["preview_type"] = "preview" if status.startswith("preview_") or status == "rendered" else "unknown"
            item["production_asset"] = False
            item["truth_level"] = "simulated" if "simulated" in status else ("real_provider" if "real" in status else "unknown")
            voice_assets.append(item)
        conn.close()
    except Exception:
        pass

    # Schedule
    schedule = []
    schedule_readiness = {
        "status": "unknown",
        "truth_level": "unknown",
        "blocked_by": "no schedule rows found",
        "message": "Schedule/readiness is unknown until existing schedule rows are loaded."
    }
    try:
        schedule = db.get_playout_schedule()
        if schedule:
            schedule_readiness = {
                "status": "partial",
                "truth_level": "database_stored",
                "blocked_by": "AzuraCast/live playout not verified from Neena Lab endpoint",
                "message": f"{len(schedule)} schedule rows found in local database. Broadcast readiness still requires owner/AzuraCast verification."
            }
    except Exception:
        pass

    # Playout-ready items (approved items from approval queue)
    playout_ready = []
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM approval_queue WHERE status = 'approved' ORDER BY id DESC LIMIT 20")
        for row in cursor.fetchall():
            playout_ready.append(dict(row))
        conn.close()
    except Exception:
        pass

    # Source tool readiness — report which tools are registered
    source_tools = []
    try:
        from services.content.source_tools import get_source_tool_readiness
        source_tools = get_source_tool_readiness().get("tools", [])
    except Exception:
        pass

    # Recent activity
    activity = []
    try:
        recent = db.get_recent_activities(limit=15)
        for act in recent:
            activity.append({
                "timestamp": act.get("timestamp", ""),
                "type": act.get("type", ""),
                "detail": act.get("detail", "")
            })
    except Exception:
        pass

    # Broadcast capsules (M4-A1)
    broadcast_capsules = []
    broadcast_readiness = {}
    try:
        from services.broadcast.capsule_service import list_recent_capsules
        from services.voice.gen_service import get_broadcast_audio_readiness
        broadcast_capsules = list_recent_capsules(limit=20)
        broadcast_readiness = get_broadcast_audio_readiness()
    except Exception:
        pass

    return {
        "mode": mode,
        "current_task": current_task,
        "script_drafts": script_drafts,
        "approval_queue": approval_queue,
        "voice_assets": voice_assets,
        "schedule": schedule,
        "schedule_readiness": schedule_readiness,
        "playout_ready": playout_ready,
        "approved_scripts": playout_ready,
        "broadcast_capsules": broadcast_capsules,
        "broadcast_readiness": broadcast_readiness,
        "source_tools": source_tools,
        "activity": activity
    }


# --- Health and Readiness Check Endpoints ---
@app.get("/healthz")
@app.get("/api/healthz")
async def healthz():
    """Lightweight health check that returns instantly without dependencies."""
    return {"ok": True, "service": "neena-backend"}


@app.get("/readyz")
@app.get("/api/readyz")
def readyz(response: Response):
    """Lightweight readiness check verifying local SQLite DB, Postgres, and Redis with strict timeouts."""
    status = {"ok": True, "service": "neena-backend", "checks": {}}

    # 1. SQLite DB check
    try:
        conn = db.get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        status["checks"]["sqlite"] = {"available": True}
    except Exception as e:
        status["checks"]["sqlite"] = {"available": False, "error": str(e)}
        status["ok"] = False

    # 2. Postgres Check
    try:
        import psycopg2
        pg_conn = psycopg2.connect(
            host=os.environ.get("NEENA_PG_HOST", "neena-postgres"),
            port=int(os.environ.get("NEENA_PG_PORT", "5432")),
            dbname=os.environ.get("NEENA_PG_DB", "neena_memory_shadow"),
            user=os.environ.get("NEENA_PG_USER", "neena_shadow"),
            password=os.environ.get("NEENA_PG_PASSWORD", "neena_shadow_dev"),
            connect_timeout=2
        )
        cursor = pg_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        pg_conn.close()
        status["checks"]["postgres"] = {"available": True}
    except Exception as e:
        status["checks"]["postgres"] = {"available": False, "error": str(e)}
        status["ok"] = False

    # 3. Redis Check
    try:
        import redis
        r = redis.Redis(
            host=os.environ.get("NEENA_REDIS_HOST", "neena-redis"),
            port=int(os.environ.get("NEENA_REDIS_PORT", "6379")),
            socket_timeout=2.0
        )
        r.ping()
        try:
            r.close()
        except Exception:
            pass
        status["checks"]["redis"] = {"available": True}
    except Exception as e:
        status["checks"]["redis"] = {"available": False, "error": str(e)}
        status["ok"] = False

    if not status["ok"]:
        response.status_code = 503

    return status


@app.websocket("/api/neena/live-voice")
async def websocket_live_voice(websocket: WebSocket):
    from services.brain.live_voice import handle_live_voice_websocket
    await handle_live_voice_websocket(websocket)


# Serve static dashboard files directly from root
from fastapi.staticfiles import StaticFiles

# Mount playout folder for static audio file playback
PLAYOUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "playout"))
os.makedirs(PLAYOUT_DIR, exist_ok=True)
app.mount("/playout", StaticFiles(directory=PLAYOUT_DIR), name="playout")

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

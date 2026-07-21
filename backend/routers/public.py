"""Public listener + app-config HTTP domain.

Single responsibility: endpoints consumed by the public mobile app and inbound
listener webhooks (now-playing, market rates, schedule, dedications, birthday
wishes, remote app-config). Rate-limited via the shared limiter.
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

import database as db
from app_core import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


class MarketRateUpdate(BaseModel):
    price: str
    trend: str
    price_change: str


class SongDedicationRequest(BaseModel):
    listener_name: str
    region: str
    dedicated_to: str
    song_title: str
    message: Optional[str] = ""


class BirthdayWishRequest(BaseModel):
    listener_name: str
    region: str
    wish_for: str
    message: Optional[str] = ""


class AppConfigUpdate(BaseModel):
    value: str


@router.post("/api/leads/inbound-webhook")
@limiter.limit("20/minute")
def leads_inbound_webhook(request: Request, data: dict = Body(...)):
    """Public/listener WhatsApp — role=customer via message router (not owner path)."""
    import time
    from services.cockpit.recorder import record_whatsapp_turn
    from services.brain.message_router import process_message

    phone = data.get("phone", "")
    message = data.get("message", "")
    sender_name = data.get("sender_name", "ji")
    if not message:
        raise HTTPException(status_code=400, detail="Missing message")

    db.add_activity_log("lead", f"Inbound WhatsApp lead from {sender_name} ({phone}): '{message[:80]}'")
    started = time.monotonic()
    result = process_message(
        role="customer", message=message, sender_name=sender_name, phone=phone,
    )
    reply_text = (result.get("reply") or "").strip()
    latency_ms = round((time.monotonic() - started) * 1000)
    try:
        record_whatsapp_turn(
            user_input=message, result=result, latency_ms=latency_ms, is_owner=False,
        )
    except Exception:
        logger.exception("Failed to record listener WhatsApp turn")
    return {"reply": reply_text, "action_type": result.get("action_type")}


@router.post("/api/public/whatsapp-inbound")
@limiter.limit("20/minute")
def public_whatsapp_inbound(request: Request, data: dict = Body(...)):
    """
    Alias endpoint for public WhatsApp inbound message flow.
    """
    return leads_inbound_webhook(request, data)


@router.get("/api/market-rates")
def get_market_rates():
    return db.get_market_rates()


@router.put("/api/market-rates/{item_name}")
def update_market_rate(item_name: str, data: MarketRateUpdate):
    db.update_market_rate(
        item_name=item_name,
        price=data.price,
        trend=data.trend,
        price_change=data.price_change
    )
    return {"status": "success", "message": f"Updated {item_name} successfully"}


@router.get("/api/public/now-playing")
@limiter.limit("5/minute")
def public_now_playing(request: Request):
    """Endpoint for public mobile application to query what is currently on-air"""
    try:
        from services.broadcast.azuracast_client import get_azuracast_status
        azura = get_azuracast_status()
    except Exception:
        azura = {}
    stream_url = azura.get("stream_url", "")
    if not stream_url or stream_url == "(not set)":
        stream_url = os.environ.get("STREAM_PUBLIC_URL", "")
    truth = azura.get("truth_level", "unknown")
    # Mount live + metadata missing is not "failed" for listeners.
    if truth == "failed" and azura.get("stream_reachable"):
        truth = "stream_reachable"
    title = azura.get("now_playing_title") or "Orai Radio Live"
    artist = azura.get("now_playing_artist") or "On Air"
    if truth == "stream_reachable" and title in ("Unknown", "", None):
        title = "Orai Radio Live"
        artist = "Stream online"
    return {
        "title": title,
        "artist": artist,
        "stream_url": stream_url,
        "truth_level": truth,
        "stream_reachable": bool(azura.get("stream_reachable")),
    }


@router.get("/api/public/market-rates")
@limiter.limit("5/minute")
def public_market_rates(request: Request):
    """Endpoint for public mobile application to query mandi and gold rates"""
    return db.get_market_rates()


@router.get("/api/public/schedule")
@limiter.limit("5/minute")
def public_schedule(request: Request):
    """Endpoint for public mobile application to query the current playout schedule"""
    try:
        schedule = db.get_playout_schedule()
        return {"status": "success", "schedule": schedule}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch schedule: {str(e)}")


@router.post("/api/public/dedicate")
@limiter.limit("5/minute")
def public_dedicate(request: Request, data: SongDedicationRequest):
    """Endpoint for public mobile application to request song dedication"""
    if not data.listener_name.strip() or not data.region.strip() or not data.dedicated_to.strip() or not data.song_title.strip():
        raise HTTPException(status_code=400, detail="All fields except message are required.")

    db.add_song_dedication(
        listener_name=data.listener_name.strip(),
        region=data.region.strip(),
        dedicated_to=data.dedicated_to.strip(),
        song_title=data.song_title.strip(),
        message=data.message.strip() if data.message else ""
    )

    db.add_activity_log(
        "dedication",
        f"New Dedication: '{data.song_title}' requested by {data.listener_name} ({data.region}) for {data.dedicated_to}"
    )

    return {"status": "success", "message": "Song dedication request received successfully."}


@router.post("/api/public/song-request")
@limiter.limit("5/minute")
def public_song_request(request: Request, data: SongDedicationRequest):
    """Alias for public song dedication endpoint"""
    return public_dedicate(request, data)


@router.post("/api/public/birthday-wish")
@limiter.limit("5/minute")
def public_birthday_wish(request: Request, data: BirthdayWishRequest):
    """Endpoint for public mobile application to request birthday wish announcements"""
    if not data.listener_name.strip() or not data.region.strip() or not data.wish_for.strip():
        raise HTTPException(status_code=400, detail="All fields except message are required.")

    db.add_birthday_wish(
        listener_name=data.listener_name.strip(),
        region=data.region.strip(),
        wish_for=data.wish_for.strip(),
        message=data.message.strip() if data.message else ""
    )

    db.add_activity_log(
        "birthday_wish",
        f"New Birthday Wish: for '{data.wish_for}' requested by {data.listener_name} ({data.region})"
    )

    return {"status": "success", "message": "Birthday wish request received successfully."}


@router.get("/api/public/app-config")
@limiter.limit("20/minute")
def public_app_config(request: Request):
    """Endpoint to retrieve remote configuration for the mobile app"""
    try:
        config = db.get_app_config()
        if not config:
            raise Exception("Empty config")
        return config
    except Exception as e:
        logger.error(f"Failed to fetch app config from db: {e}")
        return {
            "api_base_url": os.environ.get("APP_API_BASE_URL", "http://35.244.15.150:8080"),
            "stream_url": os.environ.get("STREAM_PUBLIC_URL", "http://35.244.15.150/listen/orai_radio/radio.mp3"),
            "backup_stream_url": "",
            "maintenance_mode": False,
            "maintenance_message": "Orai Radio is under maintenance. We will be back online soon!",
            "force_update": False,
            "minimum_supported_version": 1
        }


@router.get("/api/business-config")
def get_current_business_config():
    """Returns the current active business profile metadata dynamically."""
    from services.brain.prompt_builder import get_business_config
    return get_business_config()


@router.put("/api/admin/app-config/{key}")
def update_app_config_endpoint(key: str, data: AppConfigUpdate, request: Request):
    """Endpoint for admin dashboard or scripts to dynamically update app config parameters"""
    auth_header = request.headers.get("Authorization")
    token = (os.environ.get("APP_CONFIG_ADMIN_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="APP_CONFIG_ADMIN_TOKEN not configured")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    provided_token = auth_header.split(" ", 1)[1].strip()
    if provided_token != token:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid token")

    try:
        db.update_app_config(key, data.value)
        return {"status": "success", "message": f"Updated config '{key}' successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

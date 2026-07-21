"""
Orai Radio — Local Source Tool Contracts v1

Modular local source tool implementations with safe fallback/manual/unavailable behavior.
Every tool returns structured JSON with `status` and `truth_level`.
No paid/external API integration yet — only contracts and safe fallback data.

Rules:
- Never fake traffic, weather, real news, sponsors, listener names, farmaish, stream status, or broadcast success.
- Evergreen content ideas can be returned as safe fallback, but must be labeled as fallback/evergreen, not live news.
- If real source/API is missing, return unavailable, fallback, manual_required, or unknown.
"""

import os
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


def _is_configured_value(value: str) -> bool:
    if not value:
        return False
    lowered = str(value).lower()
    return not any(marker in lowered for marker in ["your_", "placeholder", "here", "changeme"])


def _readiness_entry(
    tool_name: str,
    label: str,
    status: str,
    truth_level: str,
    real_source_configured: bool,
    fallback_available: bool,
    manual_available: bool,
    blocked_by: str = "",
    message: str = "",
) -> dict:
    return {
        "tool_name": tool_name,
        "label": label,
        "status": status,
        "truth_level": truth_level,
        "real_source_configured": real_source_configured,
        "fallback_available": fallback_available,
        "manual_available": manual_available,
        "blocked_by": blocked_by,
        "message": message,
    }


def get_local_traffic_update(city="Orai", area=None, time_window="now") -> dict:
    """
    Get traffic/road condition information for Orai-relevant areas.
    Currently: no real source connected. Returns unavailable/manual_required.
    """
    return {
        "tool_name": "get_local_traffic_update",
        "status": "unavailable",
        "truth_level": "manual_required",
        "real_source_configured": False,
        "fallback_available": False,
        "manual_available": True,
        "blocked_by": "traffic API/manual feed not configured",
        "data": {
            "city": city,
            "area": area,
            "time_window": time_window,
            "traffic_level": "unknown",
            "summary": "Real-time traffic data source is not configured. Owner/team manual input required.",
            "source": "none"
        },
        "message": "Traffic update source not connected. Manual input needed."
    }


def get_local_weather(city="Orai", time_window="today") -> dict:
    """
    Get Orai weather for RJ bulletins.
    Currently: no weather API configured. Returns unavailable.
    """
    return {
        "tool_name": "get_local_weather",
        "status": "unavailable",
        "truth_level": "unknown",
        "real_source_configured": False,
        "fallback_available": False,
        "manual_available": True,
        "blocked_by": "weather API not configured",
        "data": {
            "city": city,
            "time_window": time_window,
            "temperature": None,
            "condition": "unknown",
            "summary": "Weather API is not configured. Cannot provide real weather data.",
            "source": "none"
        },
        "message": "Weather source not connected. API key/configuration needed."
    }


def get_local_news_events(city="Orai", category="general", time_window="today") -> dict:
    """
    Collect public-safe local updates and events.
    Currently: no real news source connected. Returns unavailable.
    """
    return {
        "tool_name": "get_local_news_events",
        "status": "unavailable",
        "truth_level": "unknown",
        "real_source_configured": False,
        "fallback_available": False,
        "manual_available": True,
        "blocked_by": "approved RSS/API/manual feed not configured",
        "items": [],
        "data": {
            "city": city,
            "category": category,
            "time_window": time_window
        },
        "message": "Local news source not connected. No approved RSS/API configured."
    }


def get_market_rates(market="Orai", category="mandi") -> dict:
    """
    Get mandi/sarafa rates from existing database.
    This tool can return real data from the database if available.
    """
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        import database as db

        rates = db.get_market_rates()
        if category and category != "all":
            rates = [r for r in rates if r.get("category", "").lower() == category.lower()]

        if rates:
            rate_items = []
            for r in rates:
                rate_items.append({
                    "item": r.get("item_name", ""),
                    "value": r.get("price", ""),
                    "unit": r.get("unit", ""),
                    "trend": r.get("trend", ""),
                    "price_change": r.get("price_change", ""),
                    "updated_at": "database_stored"
                })
            return {
                "tool_name": "get_market_rates",
                "status": "success",
                "truth_level": "owner_provided",
                "real_source_configured": True,
                "fallback_available": False,
                "manual_available": True,
                "blocked_by": "freshness must be checked manually before broadcast",
                "rates": rate_items,
                "message": f"Found {len(rate_items)} rate items from database. Freshness is not timestamped."
            }
        else:
            return {
                "tool_name": "get_market_rates",
                "status": "success",
                "truth_level": "unknown",
                "real_source_configured": True,
                "fallback_available": False,
                "manual_available": True,
                "blocked_by": "no rates in database for this category",
                "rates": [],
                "message": "No rates found in database for the given category."
            }
    except Exception as e:
        logger.error(f"get_market_rates error: {e}")
        return {
            "tool_name": "get_market_rates",
            "status": "failed",
            "truth_level": "unknown",
            "real_source_configured": False,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "database read failed",
            "rates": [],
            "message": f"Failed to fetch market rates: {str(e)}"
        }


def get_day_context(target_date="today", city="Orai") -> dict:
    """
    Get day context: day name, known festivals, local events.
    Uses Python datetime for day name. Festival/event data is limited to basic calendar.
    """
    try:
        if target_date == "today":
            d = date.today()
        else:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()

        day_names_hi = {
            0: "Somvar (Monday)",
            1: "Mangalvar (Tuesday)",
            2: "Budhvar (Wednesday)",
            3: "Guruvar (Thursday)",
            4: "Shukravar (Friday)",
            5: "Shanivar (Saturday)",
            6: "Ravivar (Sunday)"
        }

        day_name = day_names_hi.get(d.weekday(), d.strftime("%A"))

        return {
            "tool_name": "get_day_context",
            "status": "success",
            "truth_level": "real_verified",
            "real_source_configured": True,
            "fallback_available": True,
            "manual_available": True,
            "blocked_by": "festival/local event calendar not connected",
            "data": {
                "date": d.isoformat(),
                "day_name": day_name,
                "festival": None,
                "local_events": [],
                "suggested_tone": "normal",
                "city": city
            },
            "message": "Day/date from system calendar. Festival/event data not yet connected."
        }
    except Exception as e:
        return {
            "tool_name": "get_day_context",
            "status": "failed",
            "truth_level": "unknown",
            "real_source_configured": False,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "date parsing failed",
            "data": {},
            "message": f"Failed to get day context: {str(e)}"
        }


def get_public_requests(status_filter="pending", request_type=None) -> dict:
    """
    Get public farmaish, birthday wishes, greetings from existing database tables.
    Returns real data from song_dedications and birthday_wishes tables.
    """
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        import database as db

        items = []

        # Song dedications
        dedications = db.get_pending_dedications(limit=10)
        for d in dedications:
            items.append({
                "type": "song_request",
                "listener_name": d.get("listener_name", ""),
                "region": d.get("region", ""),
                "details": d.get("song_title", ""),
                "dedicated_to": d.get("dedicated_to", ""),
                "message": d.get("message", ""),
                "status": d.get("status", "pending"),
                "created_at": d.get("created_at", "")
            })

        # Birthday wishes
        wishes = db.get_pending_birthday_wishes(limit=10)
        for w in wishes:
            items.append({
                "type": "birthday",
                "listener_name": w.get("listener_name", ""),
                "region": w.get("region", ""),
                "details": w.get("wish_for", ""),
                "message": w.get("message", ""),
                "status": w.get("status", "pending"),
                "created_at": w.get("created_at", "")
            })

        if request_type:
            items = [i for i in items if i["type"] == request_type]

        return {
            "tool_name": "get_public_requests",
            "status": "success",
            "truth_level": "real_verified",
            "real_source_configured": True,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "" if items else "no pending public requests found",
            "items": items,
            "message": f"Found {len(items)} public requests from database."
        }
    except Exception as e:
        logger.error(f"get_public_requests error: {e}")
        return {
            "tool_name": "get_public_requests",
            "status": "failed",
            "truth_level": "unknown",
            "real_source_configured": False,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "database read failed",
            "items": [],
            "message": f"Failed to fetch public requests: {str(e)}"
        }


def get_sponsor_ad_inventory(target_date="today", status_filter="active") -> dict:
    """
    Get active sponsor campaigns from existing database.
    Returns real data from sponsor_campaigns table.
    """
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        import database as db

        if target_date == "today":
            d = date.today().isoformat()
        else:
            d = target_date

        campaigns = db.get_active_campaigns(d)
        campaign_items = []
        for c in campaigns:
            campaign_items.append({
                "sponsor_name": c.get("sponsor_name", ""),
                "campaign_name": c.get("campaign_name", ""),
                "start_date": c.get("start_date", ""),
                "end_date": c.get("end_date", ""),
                "audio_file": c.get("audio_file_path", ""),
                "play_slots_limit": c.get("play_slots_limit", 0),
                "is_active": bool(c.get("is_active", 0))
            })

        return {
            "tool_name": "get_sponsor_ad_inventory",
            "status": "success",
            "truth_level": "unknown",
            "real_source_configured": True,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "campaign provenance/approval must be manually verified before broadcast" if campaign_items else "no active sponsor campaigns found",
            "campaigns": campaign_items,
            "message": f"Found {len(campaign_items)} active campaigns for {d}. Manual verification required before broadcast use."
        }
    except Exception as e:
        logger.error(f"get_sponsor_ad_inventory error: {e}")
        return {
            "tool_name": "get_sponsor_ad_inventory",
            "status": "failed",
            "truth_level": "unknown",
            "real_source_configured": False,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "database read failed",
            "campaigns": [],
            "message": f"Failed to fetch sponsor campaigns: {str(e)}"
        }


def get_evergreen_content_ideas(slot="morning", tone="energetic", duration_seconds=30) -> dict:
    """
    Provide safe filler content ideas when live sources are empty.
    These are labeled as evergreen/fallback, not live news.
    """
    ideas_library = {
        "morning": {
            "energetic": [
                "Bundeli Good Morning capsule — 'Jai Bundeli! Orai ki subah energy ke saath shuru!'",
                "Motivation minute — '30 second ki himmat, pura din ka joshila safar'",
                "Local culture fact — 'Kya aap jaante hain? Orai ke baare mein ek dilchasp baat'",
            ],
            "calm": [
                "Soft morning greeting — 'Shanti aur sukoon ke saath Orai Radio ki subah'",
                "Health tip — 'Subah ki chai ke saath ek healthy sujhav'",
            ],
            "funny": [
                "Bundeli comedy filler — 'Hasi ka dose, Orai style mein!'",
                "Funny local observation — 'Chowk ki kahani, Bundeli zubani'",
            ],
        },
        "afternoon": {
            "energetic": [
                "Dopahar energy burst — 'Dopahar ki dhoop mein thanda joshila break!'",
                "Quick trivia — 'Orai ka GK, 30 second mein'",
            ],
            "calm": [
                "Afternoon calm capsule — 'Thoda sukoon, thodi mithaas, Orai Radio ke saath'",
            ],
            "informative": [
                "Public safety tip — 'Garmi mein paani peete rahein, sehat ka dhyan rakhein'",
            ],
        },
        "evening": {
            "energetic": [
                "Evening local capsule — 'Shaam ki taazi hawa, Orai Radio ke saath'",
                "Market recap teaser — 'Aaj bazaar mein kya raha, suniye shaam ka review'",
            ],
            "funny": [
                "Comedy capsule — 'Shaam ke mazze, Bundeli andaaz mein'",
            ],
        },
        "night": {
            "calm": [
                "Good night capsule — 'Orai Radio kehta hai, shubh ratri, kal phir milenge!'",
                "Tomorrow teaser — 'Kal ki subah kya laayegi? Orai Radio ke saath rahen!'",
            ],
        },
    }

    slot_ideas = ideas_library.get(slot, ideas_library.get("morning", {}))
    tone_ideas = slot_ideas.get(tone, [])

    # If no ideas for specific tone, collect all ideas for the slot
    if not tone_ideas:
        for t_ideas in slot_ideas.values():
            tone_ideas.extend(t_ideas)

    return {
        "tool_name": "get_evergreen_content_ideas",
        "status": "success",
        "truth_level": "evergreen_safe",
        "real_source_configured": True,
        "fallback_available": True,
        "manual_available": True,
        "blocked_by": "",
        "ideas": tone_ideas,
        "data": {
            "slot": slot,
            "tone": tone,
            "duration_seconds": duration_seconds
        },
        "message": f"Found {len(tone_ideas)} evergreen content ideas for {slot}/{tone}. These are safe fallback content, not live news."
    }


def plan_show_rotation(target_date="today", station_style="Orai local entertainment",
                       available_content=None, ad_slots=None) -> dict:
    """
    Plan a 24-hour content rotation to prevent repetitive content.
    Returns a suggested block-wise plan using available tools and content.
    """
    if target_date == "today":
        d = date.today().isoformat()
    else:
        d = target_date

    suggested_blocks = [
        {
            "time": "05:00-07:00",
            "theme": "Early Morning Devotional & Soft Start",
            "content_needed": ["devotional", "day_greeting"],
            "source_tools": ["get_day_context", "get_evergreen_content_ideas"],
            "status": "draft"
        },
        {
            "time": "07:00-09:00",
            "theme": "Morning Local Start",
            "content_needed": ["weather", "day_greeting", "mandi_preview", "short_rj_intro"],
            "source_tools": ["get_local_weather", "get_day_context", "get_market_rates"],
            "status": "draft"
        },
        {
            "time": "09:00-11:00",
            "theme": "Mid-Morning Info & Light Entertainment",
            "content_needed": ["local_info", "traffic", "light_comedy"],
            "source_tools": ["get_local_news_events", "get_local_traffic_update", "get_evergreen_content_ideas"],
            "status": "draft"
        },
        {
            "time": "11:00-13:00",
            "theme": "Mandi Report & Sponsor Block",
            "content_needed": ["mandi_rates", "sponsor_ads"],
            "source_tools": ["get_market_rates", "get_sponsor_ad_inventory"],
            "status": "draft"
        },
        {
            "time": "13:00-16:00",
            "theme": "Afternoon Music & Evergreen Capsules",
            "content_needed": ["music", "evergreen_capsules", "sponsor_ads"],
            "source_tools": ["get_evergreen_content_ideas", "get_sponsor_ad_inventory"],
            "status": "draft"
        },
        {
            "time": "16:00-18:00",
            "theme": "Evening Traffic & Market Recap",
            "content_needed": ["traffic", "market_recap", "comedy"],
            "source_tools": ["get_local_traffic_update", "get_market_rates", "get_evergreen_content_ideas"],
            "status": "draft"
        },
        {
            "time": "18:00-20:00",
            "theme": "Farmaish & Listener Connect",
            "content_needed": ["public_requests", "birthday_wishes", "dedications"],
            "source_tools": ["get_public_requests"],
            "status": "draft"
        },
        {
            "time": "20:00-22:00",
            "theme": "Night Calm & Old Memories",
            "content_needed": ["calm_rj", "evergreen_capsules"],
            "source_tools": ["get_evergreen_content_ideas"],
            "status": "draft"
        },
        {
            "time": "22:00-05:00",
            "theme": "Overnight Music & Filler",
            "content_needed": ["music_rotation", "next_day_teaser"],
            "source_tools": ["get_evergreen_content_ideas"],
            "status": "draft"
        }
    ]

    return {
        "tool_name": "plan_show_rotation",
        "status": "success",
        "truth_level": "fallback",
        "real_source_configured": True,
        "fallback_available": True,
        "manual_available": True,
        "blocked_by": "draft rotation only; not scheduled or broadcast",
        "data": {
            "date": d,
            "station_style": station_style,
            "blocks": suggested_blocks
        },
        "message": f"Suggested 24-hour rotation plan for {d}. All blocks are draft — real source data needs to be checked per block."
    }


def check_stream_health(stream_url=None) -> dict:
    """
    Check if the configured stream is reachable.
    Uses the AzuraCast client for the actual check.
    """
    try:
        from services.broadcast.azuracast_client import get_azuracast_status
        azura = get_azuracast_status()

        return {
            "tool_name": "check_stream_health",
            "status": "reachable" if azura.get("stream_reachable") else "unreachable",
            "truth_level": azura.get("truth_level", "unknown"),
            "real_source_configured": bool(azura.get("configured", False)),
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "" if azura.get("configured") else "stream/AzuraCast URL not configured",
            "data": {
                "configured": azura.get("configured", False),
                "stream_url": azura.get("stream_url", "(not set)"),
                "stream_reachable": azura.get("stream_reachable", False),
                "icecast_status": azura.get("icecast_status", "unknown"),
                "now_playing": azura.get("now_playing_title", None),
                "listeners": azura.get("listener_count", 0),
                "checked_at": datetime.now().isoformat(),
                "notes": azura.get("notes", [])
            },
            "message": "Stream health checked." if azura.get("configured") else "Stream URL not configured."
        }
    except Exception as e:
        logger.error(f"check_stream_health error: {e}")
        return {
            "tool_name": "check_stream_health",
            "status": "unknown",
            "truth_level": "failed",
            "real_source_configured": False,
            "fallback_available": False,
            "manual_available": True,
            "blocked_by": "stream health check failed",
            "data": {
                "http_status": None,
                "now_playing": None,
                "checked_at": datetime.now().isoformat()
            },
            "message": f"Stream health check failed: {str(e)}"
        }


def get_source_tool_readiness() -> dict:
    """
    Return source-tool readiness without live network calls or generated content.
    This is safe for Neena Lab and owner status commands.
    """
    weather_configured = _is_configured_value(os.environ.get("WEATHER_API_KEY", ""))
    traffic_configured = _is_configured_value(os.environ.get("TRAFFIC_API_KEY", ""))
    news_configured = _is_configured_value(os.environ.get("LOCAL_NEWS_RSS_URL", ""))
    azuracast_configured = _is_configured_value(os.environ.get("AZURACAST_BASE_URL", "")) and _is_configured_value(os.environ.get("AZURACAST_STREAM_URL", ""))

    try:
        rates = get_market_rates(market="Orai", category="all")
    except Exception:
        rates = {"status": "failed", "truth_level": "unknown", "rates": []}

    try:
        public_requests = get_public_requests()
    except Exception:
        public_requests = {"status": "failed", "truth_level": "unknown", "items": []}

    try:
        sponsors = get_sponsor_ad_inventory()
    except Exception:
        sponsors = {"status": "failed", "truth_level": "unknown", "campaigns": []}

    tools = [
        _readiness_entry(
            "get_local_traffic_update",
            "Traffic",
            "unavailable" if not traffic_configured else "configured_check_required",
            "manual_required" if not traffic_configured else "unknown",
            traffic_configured,
            False,
            True,
            "" if traffic_configured else "traffic API/manual feed not configured",
            "No live traffic claim will be generated without configured source or manual input.",
        ),
        _readiness_entry(
            "get_local_weather",
            "Weather",
            "unavailable" if not weather_configured else "configured_check_required",
            "unknown",
            weather_configured,
            False,
            True,
            "" if weather_configured else "weather API not configured",
            "Weather capsule requires real API result or manual owner input.",
        ),
        _readiness_entry(
            "get_local_news_events",
            "Local news/events",
            "unavailable" if not news_configured else "configured_check_required",
            "unknown",
            news_configured,
            False,
            True,
            "" if news_configured else "approved news/event source not configured",
            "Local news/events require verified source or owner-provided item.",
        ),
        _readiness_entry(
            "get_market_rates",
            "Mandi/Sarafa",
            rates.get("status", "unknown"),
            rates.get("truth_level", "unknown"),
            True,
            False,
            True,
            rates.get("blocked_by", "freshness must be checked manually before broadcast"),
            rates.get("message", ""),
        ),
        _readiness_entry(
            "get_day_context",
            "Festival/calendar",
            "partial",
            "real_verified",
            True,
            True,
            True,
            "festival/local event calendar not connected",
            "Date/day is real from system calendar; festival/local event data is not connected.",
        ),
        _readiness_entry(
            "get_public_requests",
            "Public requests",
            public_requests.get("status", "unknown"),
            public_requests.get("truth_level", "unknown"),
            True,
            False,
            True,
            public_requests.get("blocked_by", ""),
            public_requests.get("message", ""),
        ),
        _readiness_entry(
            "get_sponsor_ad_inventory",
            "Sponsors/ads",
            sponsors.get("status", "unknown"),
            sponsors.get("truth_level", "unknown"),
            True,
            False,
            True,
            sponsors.get("blocked_by", "campaign provenance/approval must be manually verified before broadcast"),
            sponsors.get("message", ""),
        ),
        _readiness_entry(
            "get_evergreen_content_ideas",
            "Evergreen local content",
            "success",
            "evergreen_safe",
            True,
            True,
            True,
            "",
            "Safe filler ideas are available but must not be presented as live news.",
        ),
        _readiness_entry(
            "plan_show_rotation",
            "Show rotation",
            "success",
            "fallback",
            True,
            True,
            True,
            "draft rotation only; not scheduled or broadcast",
            "Can draft a rotation; owner approval/scheduling remains separate.",
        ),
        _readiness_entry(
            "check_stream_health",
            "Stream/now-playing",
            "configured_check_required" if azuracast_configured else "unavailable",
            "unknown",
            azuracast_configured,
            False,
            True,
            "" if azuracast_configured else "AzuraCast base/stream URL not configured",
            "Live stream status requires explicit read-only check.",
        ),
    ]

    return {
        "status": "success",
        "truth_level": "readiness_only",
        "tools": tools,
        "checked_at": datetime.now().isoformat(),
        "message": "Source tool readiness only; no live creative content or broadcast action was generated.",
    }

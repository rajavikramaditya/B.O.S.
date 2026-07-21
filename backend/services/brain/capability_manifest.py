import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
import services.llm.provider_router as pr
import services.cockpit.runtime_controller as rc
import services.content.source_tools as st

logger = logging.getLogger(__name__)

def build_capability_manifest() -> dict:
    """
    Builds a list of actual system capabilities based on real backend code,
    tool configurations, database access, and LLM configuration states.
    """
    llm_configured = pr.is_llm_configured()
    
    # Check configurations from environment
    weather_key = os.environ.get("WEATHER_API_KEY", "")
    traffic_key = os.environ.get("TRAFFIC_API_KEY", "")
    news_rss = os.environ.get("LOCAL_NEWS_RSS_URL", "")
    
    weather_api_ok = bool(weather_key and "placeholder" not in weather_key.lower() and "change" not in weather_key.lower())
    traffic_api_ok = bool(traffic_key and "placeholder" not in traffic_key.lower() and "change" not in traffic_key.lower())
    news_rss_ok = bool(news_rss and "placeholder" not in news_rss.lower() and "change" not in news_rss.lower())
    
    # Check ElevenLabs TTS config
    eleven_key = os.environ.get("ELEVEN_LABS_API_KEY", "")
    tts_real_configured = bool(eleven_key and "placeholder" not in eleven_key.lower() and "change" not in eleven_key.lower())

    # Owner WhatsApp push: available only when owner number configured.
    owner_wa_number = "".join(c for c in os.environ.get("OWNER_WHATSAPP_NUMBER", "") if c.isdigit())
    owner_wa_configured = bool(owner_wa_number)

    capabilities = [
        {
            "capability_id": "station_status",
            "label": "Read Station/Center Status",
            "category": "station_status",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "run_diagnostics",
            "source_of_truth": "SQLite station_runtime_status and database logs",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "diagnostics",
            "label": "Run Station Diagnostics",
            "category": "diagnostics",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "run_diagnostics",
            "source_of_truth": "Local system metrics and service checks",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "check_interaction_recorder",
            "label": "Read Interaction Recorder (self-check)",
            "category": "diagnostics",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "check_interaction_recorder",
            "source_of_truth": "command_center_turns recorder (owner-only summary)",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "stream_status",
            "label": "Check Stream Health & Now Playing",
            "category": "stream_status",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "check_stream_health",
            "source_of_truth": "AzuraCast Icecast client API",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "source_tools_status",
            "label": "Get Source Tools Readiness",
            "category": "source_tools_status",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "get_source_tool_readiness",
            "source_of_truth": "Local environmental and database checks",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "market_rates",
            "label": "Read & Write Mandi/Sarafa Rates",
            "category": "market_rates",
            "available_now": True,
            "mode": "safe_write",
            "tool_name": "get_market_rates / update_market_rates",
            "source_of_truth": "SQLite market_rates table",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "public_requests",
            "label": "Read Listener Dedications & Song Requests",
            "category": "public_requests",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "get_public_requests",
            "source_of_truth": "SQLite song_dedications and birthday_wishes tables",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "approval_queue",
            "label": "Read & Write Approval Queue",
            "category": "approval_queue",
            "available_now": True,
            "mode": "safe_write",
            "tool_name": "get_approval_queue / queue_script_for_approval",
            "source_of_truth": "SQLite approval_queue table",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "script_generation",
            "label": "Generate RJ script Drafts",
            "category": "script_generation",
            "available_now": llm_configured,
            "mode": "safe_write",
            "tool_name": "generate_rj_script",
            "source_of_truth": "Gemini 3.1 Flash Lite API",
            "requires_owner_approval": False,
            "blocked_reason": None if llm_configured else "Primary Gemini LLM API is offline or unconfigured",
            "truth_level": "real_verified" if llm_configured else "not_configured"
        },
        {
            "capability_id": "24_hour_planning",
            "label": "Create suggested 24-hour content plan",
            "category": "24_hour_planning",
            "available_now": llm_configured,
            "mode": "safe_write",
            "tool_name": "plan_show_rotation",
            "source_of_truth": "Gemini 3.1 Flash Lite API",
            "requires_owner_approval": False,
            "blocked_reason": None if llm_configured else "Primary Gemini LLM API is offline or unconfigured",
            "truth_level": "real_verified" if llm_configured else "not_configured"
        },
        {
            "capability_id": "style_memory_short_term",
            "label": "Remember reply-style preferences (e.g. keep it short)",
            "category": "style_memory_short_term",
            "available_now": True,
            "mode": "safe_write",
            "tool_name": "set_response_style / remember_owner_correction",
            "source_of_truth": "Redis-backed manager state (survives restart)",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "whatsapp_owner_push",
            "label": "Send status/update to owner on WhatsApp",
            "category": "whatsapp_owner_push",
            "available_now": owner_wa_configured,
            "mode": "safe_write",
            "tool_name": "owner_notifier.notify_owner",
            "source_of_truth": "Local WhatsApp gateway → owner number",
            "requires_owner_approval": False,
            "blocked_reason": None if owner_wa_configured else "OWNER_WHATSAPP_NUMBER not configured",
            "truth_level": "real_verified" if owner_wa_configured else "not_configured"
        },
        {
            "capability_id": "voice_preview",
            "label": "Render draft voice preview audio",
            "category": "voice_preview",
            "available_now": True,
            "mode": "approval_needed" if tts_real_configured else "simulated",
            "tool_name": "voice-preview endpoint",
            "source_of_truth": "ElevenLabs API or Simulated local WAV generator",
            "requires_owner_approval": True,
            "blocked_reason": None,
            "truth_level": "real_verified" if tts_real_configured else "simulated"
        },
        {
            "capability_id": "schedule_read",
            "label": "Read AzuraCast schedule/playlists/queue (managed target)",
            "category": "schedule_read",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "get_station_schedule",
            "source_of_truth": "AzuraCast schedule + playlists + queue APIs",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "schedule_write",
            "label": "Assign capsule to AzuraCast playlist (confirm)",
            "category": "schedule_write",
            "available_now": True,
            "mode": "confirm_required",
            "tool_name": "assign_capsule_to_playlist",
            "source_of_truth": "AzuraCast playlist append (not SQLite playout_schedule)",
            "requires_owner_approval": True,
            "blocked_reason": "SQLite fake daypart grid retired for owner path",
            "truth_level": "real_verified"
        },
        {
            "capability_id": "azuracast_readiness",
            "label": "Playout/streaming status query",
            "category": "azuracast_readiness",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "check_stream_health",
            "source_of_truth": "Local AzuraCast client",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "listener_path_diagnose",
            "label": "Diagnose public app listener path (stream/API URLs)",
            "category": "listener_path",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "diagnose_listener_path",
            "source_of_truth": "AzuraCast + DNS/HTTP probes + app_config",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "listener_path_fix",
            "label": "Fix frozen-app stream via remote app_config",
            "category": "listener_path",
            "available_now": True,
            "mode": "confirm_required",
            "tool_name": "set_app_listener_config",
            "source_of_truth": "SQLite app_config (no app rebuild)",
            "requires_owner_approval": True,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "whatsapp_status",
            "label": "Query WhatsApp gateway status",
            "category": "whatsapp_status",
            "available_now": True,
            "mode": "read_only",
            "tool_name": "whatsapp status",
            "source_of_truth": "Local service status and runtime stats",
            "requires_owner_approval": False,
            "blocked_reason": None,
            "truth_level": "real_verified"
        },
        {
            "capability_id": "vm_live_ops",
            "label": "VM Restart & Control Operations",
            "category": "vm_live_ops",
            "available_now": False,
            "mode": "blocked",
            "tool_name": "restart_service (vm_restart)",
            "source_of_truth": "Safety policy engine / runtime controller",
            "requires_owner_approval": True,
            "blocked_reason": "Protected VM restart/ops strictly blocked in local test mode (requires stage controlled_vm_ops)",
            "truth_level": "not_configured"
        }
    ]

    return {
        "capabilities": capabilities,
        "total_capabilities": len(capabilities),
        "available_capabilities": len([c for c in capabilities if c["available_now"]]),
        "unavailable_capabilities": len([c for c in capabilities if not c["available_now"]])
    }

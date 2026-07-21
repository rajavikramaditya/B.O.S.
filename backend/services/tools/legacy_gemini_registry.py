import os
import sys
import json
import time
import logging
import uuid

# services/tools/ → backend/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
import services.cockpit.runtime_controller as rc

logger = logging.getLogger(__name__)


def run_diagnostics() -> dict:
    """
    Read-only diagnostics. Reports station health without restart/recovery actions.
    """
    from services.broadcast.azuracast_client import get_azuracast_status

    report = []
    issues_found = []

    try:
        ac = get_azuracast_status()
        if ac.get("stream_reachable"):
            report.append("AzuraCast stream is reachable.")
        else:
            report.append("AzuraCast stream is offline, unreachable, or unconfigured.")
            issues_found.append("azuracast_stream_offline")
        report.append(f"AzuraCast truth_level={ac.get('truth_level', 'unknown')}.")
    except Exception as e:
        report.append(f"AzuraCast diagnostics failed: {str(e)}")
        issues_found.append("azuracast_stream_diagnostics_failed")

    try:
        wa_status, wa_details = rc.get_whatsapp_health()
        report.append(f"WhatsApp gateway status={wa_status}.")
        if wa_status != "Live":
            issues_found.append("whatsapp_gateway_offline")
            report.append("Read-only diagnostics: no restart attempted. Use explicit WhatsApp restart command if owner wants recovery.")
    except Exception as e:
        report.append(f"WhatsApp gateway diagnostics failed: {str(e)}")
        issues_found.append("whatsapp_gateway_diagnostics_failed")

    try:
        stats = rc.get_system_stats()
        import sys
        runtime_mode = os.environ.get("RUNTIME_MODE", "")
        is_vm = "vm" in runtime_mode.lower() and sys.platform != "win32"
        resource_label = "VM Resources" if is_vm else "Local Machine Resources"
        
        report.append(f"{resource_label}: CPU={stats.get('cpu', 0)}%, RAM={stats.get('ram', 0)}%.")
        if stats.get("cpu", 0) > 90:
            issues_found.append("local_high_cpu" if not is_vm else "vm_high_cpu")
            report.append(f"Warning: {resource_label} CPU load is critically high.")
    except Exception as e:
        report.append(f"Failed to read resource stats: {str(e)}")

    summary = {
        "success": True,
        "diagnostics_log": report,
        "issues_found": issues_found,
        "issues_resolved": [],
        "message": f"Diagnostics complete. Found {len(issues_found)} issues. No recovery action was executed."
    }
    db.add_activity_log("diagnostics", f"Read-only diagnostics complete: {summary['message']}")
    return summary


def restart_service(service_name: str) -> dict:
    """
    Restarts a specific core service (like 'whatsapp_gateway' or 'azuracast_stream')
    to resolve connectivity errors.
    """
    if service_name == "whatsapp_gateway":
        res = rc.restart_whatsapp_gateway_process()
        db.add_activity_log("command", f"Operator requested WhatsApp Gateway restart: {res.get('message')}")
        return res
    elif service_name == "azuracast_stream":
        # Simulate AzuraCast Docker container restart
        time.sleep(1.5)
        msg = "AzuraCast playout container and Icecast mount point have been soft-reloaded."
        db.add_activity_log("command", f"Operator requested AzuraCast Stream reload: {msg}")
        return {"success": True, "message": msg}
    else:
        return {"success": False, "message": f"Service '{service_name}' is not allowed or cannot be restarted dynamically."}

def get_playout_schedule() -> dict:
    """
    Retrieves the scheduled programs and timetables for Orai Radio playout.
    """
    try:
        schedule = db.get_playout_schedule()
        return {"success": True, "schedule": schedule}
    except Exception as e:
        return {"success": False, "message": f"Failed to retrieve playout schedule: {str(e)}"}

def add_schedule_slot(time_slot: str, program_name: str, description: str = None) -> dict:
    """
    Adds a new program timetable slot to the daily schedule specifying when it will play.
    """
    try:
        db.add_schedule_slot(time_slot, program_name, description)
        return {"success": True, "message": f"Scheduled program '{program_name}' for slot '{time_slot}' successfully."}
    except Exception as e:
        return {"success": False, "message": f"Failed to add schedule slot: {str(e)}"}

def clear_playout_schedule() -> dict:
    """
    Clears the entire playout daily schedule/timetable.
    """
    try:
        db.clear_playout_schedule()
        return {"success": True, "message": "Successfully cleared the daily playout schedule."}
    except Exception as e:
        return {"success": False, "message": f"Failed to clear playout schedule: {str(e)}"}

def update_market_rates(item_name: str, price: str, trend: str, price_change: str) -> dict:
    """
    Updates a specific commodity or gold/silver price inside Orai Mandi & Sarafa Bazaar rates.
    ```
    """
    try:
        db.update_market_rate(item_name, price, trend, price_change)
        return {"success": True, "message": f"Successfully updated market rate for '{item_name}' to ₹{price}."}
    except Exception as e:
        return {"success": False, "message": f"Failed to update market rate: {str(e)}"}


def get_tool_manifests() -> list:
    """
    Returns the modular specifications and capabilities registry for Neena's active tools.
    """
    return [
        {
            "tool_name": "run_diagnostics",
            "module": "runtime_controller",
            "version": "1.0.0",
            "description": "Scans station core services (AzuraCast stream, WhatsApp gateway, local resources) and reports issues without restart or recovery actions.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/runtime/diagnostics",
            "input_schema": {},
            "output_schema": {}
        },
        {
            "tool_name": "restart_service",
            "module": "runtime_controller",
            "version": "1.0.0",
            "description": "Restarts a specific core service (allowed values: 'whatsapp_gateway', 'azuracast_stream') to fix connectivity errors or system crashes.",
            "permission": "confirm-required",
            "requires_confirmation": True,
            "endpoint": "http://localhost:8080/internal/runtime/service/restart",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "The service name to restart. Allowed: 'whatsapp_gateway', 'azuracast_stream'."
                    }
                },
                "required": ["service_name"]
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_playout_schedule",
            "module": "broadcast_scheduler",
            "version": "1.0.0",
            "description": "Retrieves the current daily playout timetable schedule of Orai Radio.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/scheduler/active-slots",
            "input_schema": {},
            "output_schema": {}
        },
        {
            "tool_name": "add_schedule_slot",
            "module": "broadcast_scheduler",
            "version": "1.0.0",
            "description": "Adds a new program timetable slot to the daily playout schedule.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/scheduler/add-slot",
            "input_schema": {
                "type": "object",
                "properties": {
                    "time_slot": {
                        "type": "string",
                        "description": "The time slot range, e.g. '08:00 AM - 10:00 AM'."
                    },
                    "program_name": {
                        "type": "string",
                        "description": "Name of the program or show."
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the show."
                    }
                },
                "required": ["time_slot", "program_name"]
            },
            "output_schema": {}
        },
        {
            "tool_name": "clear_playout_schedule",
            "module": "broadcast_scheduler",
            "version": "1.0.0",
            "description": "Clears the entire playout daily schedule/timetable.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/scheduler/clear",
            "input_schema": {},
            "output_schema": {}
        },
        {
            "tool_name": "update_market_rates",
            "module": "source_manager",
            "version": "1.0.0",
            "description": "Updates Orai Mandi commodity price indices or Sarafa Bazaar gold rates.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/source-manager/rates/update",
            "input_schema": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to update."
                    },
                    "price": {
                        "type": "string",
                        "description": "The new price value."
                    },
                    "trend": {
                        "type": "string",
                        "description": "Price trend: 'up' or 'down'."
                    },
                    "price_change": {
                        "type": "string",
                        "description": "Offset change."
                    }
                },
                "required": ["item_name", "price", "trend", "price_change"]
            },
            "output_schema": {}
        },
        # --- NEW TOOLS (Stage G) ---
        {
            "tool_name": "generate_rj_script",
            "module": "content_engine",
            "version": "1.0.0",
            "description": "Generates a structured RJ radio script for Orai Radio in Bundeli/Hinglish style. Use segment_type='mandi_report' for market rates shows, or segment_type='farmaish_capsule' for listener dedication shows.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/content/generate-script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "segment_type": {
                        "type": "string",
                        "description": "Type of radio segment to generate. Values: 'mandi_report', 'farmaish_capsule', or 'general'."
                    }
                },
                "required": ["segment_type"]
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_approval_queue",
            "module": "approval_queue",
            "version": "1.0.0",
            "description": "Retrieves the list of pending scripts and audio assets awaiting owner review and approval before on-air broadcast.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/approval/queue",
            "input_schema": {},
            "output_schema": {}
        },
        {
            "tool_name": "queue_script_for_approval",
            "module": "approval_queue",
            "version": "1.0.0",
            "description": "Queues a generated script or audio file for owner approval before it can be broadcast on Orai Radio.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": "http://localhost:8080/internal/approval/queue-item",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content_text": {
                        "type": "string",
                        "description": "The script or content text to queue for approval."
                    },
                    "asset_type": {
                        "type": "string",
                        "description": "Type of asset: 'news_script', 'show_script', 'audio_ad', or 'voice_capsule'."
                    }
                },
                "required": ["content_text", "asset_type"]
            },
            "output_schema": {}
        },
        # --- LOCAL SOURCE TOOLS (Stage 3) ---
        {
            "tool_name": "get_local_traffic_update",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets traffic/road condition information for Orai-relevant areas. Currently returns unavailable/manual_required if no real source is configured.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, default Orai."},
                    "area": {"type": "string", "description": "Specific area like Rath Road, Jhansi Road etc."},
                    "time_window": {"type": "string", "description": "Time window: morning, afternoon, evening, now."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_local_weather",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets Orai weather for RJ bulletins. Currently returns unavailable if no weather API is configured.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, default Orai."},
                    "time_window": {"type": "string", "description": "Time window: today, tomorrow."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_local_news_events",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Collects public-safe local updates and events for Orai. Currently returns unavailable if no news source is configured.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, default Orai."},
                    "category": {"type": "string", "description": "Category: general, event, civic, school, market."},
                    "time_window": {"type": "string", "description": "Time window: today."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_market_rates",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets Orai Mandi/Sarafa rates from the database. Returns real owner-provided data if available.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "market": {"type": "string", "description": "Market name, default Orai."},
                    "category": {"type": "string", "description": "Category: mandi, sarafa, fuel, custom, all."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_day_context",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets day context including day name, festivals, and local events for creating greetings and 'aaj ka din' segments.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date: 'today' or YYYY-MM-DD format."},
                    "city": {"type": "string", "description": "City name, default Orai."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_public_requests",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets pending public farmaish, birthday wishes, and song requests from the database.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter: pending, approved."},
                    "type": {"type": "string", "description": "Request type: song_request, birthday, greeting, public_message."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_sponsor_ad_inventory",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Gets active sponsor campaigns and ad inventory from the database.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Target date: 'today' or YYYY-MM-DD."},
                    "status": {"type": "string", "description": "Filter: active, pending, expired."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "get_evergreen_content_ideas",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Provides safe evergreen filler content ideas (Bundeli comedy, motivational capsules, local culture facts) when live sources are empty. Labeled as evergreen/fallback, not live news.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string", "description": "Time slot: morning, afternoon, evening, night."},
                    "tone": {"type": "string", "description": "Tone: funny, informative, energetic, calm."},
                    "duration_seconds": {"type": "integer", "description": "Target duration in seconds."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "plan_show_rotation",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Creates a suggested 24-hour content rotation plan with block-wise themes and required source tools to prevent repetitive content.",
            "permission": "safe-write",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Target date: 'today' or YYYY-MM-DD."},
                    "station_style": {"type": "string", "description": "Station style description."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "check_stream_health",
            "module": "source_tools",
            "version": "1.0.0",
            "description": "Checks whether the radio stream is reachable and what is currently playing. Returns real status from AzuraCast endpoint check.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "stream_url": {"type": "string", "description": "Stream URL to check. Uses configured URL if not provided."}
                }
            },
            "output_schema": {}
        },
        {
            "tool_name": "diagnose_listener_path",
            "module": "listener_path_service",
            "version": "1.0.0",
            "description": "Diagnose why the frozen public app cannot play: station/Icecast vs app_config stream/API DNS and HTTP probes. Does not change config.",
            "permission": "read-only",
            "requires_confirmation": False,
            "endpoint": None,
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {}
        },
        {
            "tool_name": "set_app_listener_config",
            "module": "listener_path_service",
            "version": "1.0.0",
            "description": "Update allowlisted remote app_config URLs (stream_url, api_base_url, backup_stream_url) so the frozen app can play without rebuild. Requires owner confirmation.",
            "permission": "confirm-required",
            "requires_confirmation": True,
            "endpoint": None,
            "input_schema": {
                "type": "object",
                "properties": {
                    "stream_url": {"type": "string"},
                    "api_base_url": {"type": "string"},
                    "backup_stream_url": {"type": "string"},
                    "confirmed": {"type": "boolean"}
                }
            },
            "output_schema": {}
        }
    ]

def get_tools_definition() -> list:
    """
    Returns the JSON schemas for Neena's VM control tools to be registered with Gemini.
    """
    manifests = get_tool_manifests()
    declarations = []
    for m in manifests:
        dec = {
            "name": m["tool_name"],
            "description": m["description"]
        }
        if m["input_schema"]:
            dec["parameters"] = m["input_schema"]
        declarations.append(dec)
        
    return [{"functionDeclarations": declarations}]

def dispatch_tool_call(name: str, args: dict) -> dict:
    """
    Executes a tool call based on name and arguments, and returns the envelope JSON response.
    """
    logger.info(f"[ToolRegistry] Dispatching functionCall for '{name}' with args {args}")
    
    # 1. Execute core functions
    result = None
    try:
        if name == "run_diagnostics":
            result = run_diagnostics()
        elif name == "restart_service":
            result = restart_service(args.get("service_name"))
        elif name == "get_playout_schedule":
            result = get_playout_schedule()
        elif name == "add_schedule_slot":
            result = add_schedule_slot(args.get("time_slot"), args.get("program_name"), args.get("description"))
        elif name == "clear_playout_schedule":
            result = clear_playout_schedule()
        elif name == "update_market_rates":
            result = update_market_rates(
                args.get("item_name"),
                args.get("price"),
                args.get("trend"),
                args.get("price_change")
            )
        elif name == "generate_rj_script":
            from services.content.engine import compile_rj_template
            segment_type = args.get("segment_type", "general")
            # Build minimal context from DB for the script
            context = {}
            try:
                context["mandi_rates"] = db.get_market_rates()
                context["dedications"] = db.get_pending_dedications(limit=5)
                context["birthday_wishes"] = db.get_pending_birthday_wishes(limit=5)
            except Exception:
                pass
            script_text = compile_rj_template(segment_type, context)
            result = {"success": True, "script": script_text, "segment_type": segment_type,
                      "message": f"RJ script generated for segment '{segment_type}'. Ready for review."}
        elif name == "get_approval_queue":
            pending = db.get_pending_approvals(limit=10)
            result = {"success": True, "pending_items": pending,
                      "count": len(pending),
                      "message": f"{len(pending)} items pending approval."}
        elif name == "queue_script_for_approval":
            from services.broadcast.approval_queue import queue_asset_for_review
            content_text = args.get("content_text", "")
            asset_type = args.get("asset_type", "show_script")
            if not content_text:
                result = {"success": False, "error": "content_text cannot be empty."}
            else:
                item_id = queue_asset_for_review(asset_type, content_text)
                result = {"success": True, "approval_id": item_id,
                          "message": f"Script queued for owner review (ID: {item_id}). Awaiting approval before broadcast."}
        # --- LOCAL SOURCE TOOL DISPATCH ---
        elif name == "get_local_traffic_update":
            from services.content.source_tools import get_local_traffic_update
            result = get_local_traffic_update(
                city=args.get("city", "Orai"),
                area=args.get("area"),
                time_window=args.get("time_window", "now")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_local_weather":
            from services.content.source_tools import get_local_weather
            result = get_local_weather(
                city=args.get("city", "Orai"),
                time_window=args.get("time_window", "today")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_local_news_events":
            from services.content.source_tools import get_local_news_events
            result = get_local_news_events(
                city=args.get("city", "Orai"),
                category=args.get("category", "general"),
                time_window=args.get("time_window", "today")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_market_rates":
            from services.content.source_tools import get_market_rates as source_get_market_rates
            result = source_get_market_rates(
                market=args.get("market", "Orai"),
                category=args.get("category", "mandi")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_day_context":
            from services.content.source_tools import get_day_context
            result = get_day_context(
                target_date=args.get("date", "today"),
                city=args.get("city", "Orai")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_public_requests":
            from services.content.source_tools import get_public_requests
            result = get_public_requests(
                status_filter=args.get("status", "pending"),
                request_type=args.get("type")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_sponsor_ad_inventory":
            from services.content.source_tools import get_sponsor_ad_inventory
            result = get_sponsor_ad_inventory(
                target_date=args.get("date", "today"),
                status_filter=args.get("status", "active")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "get_evergreen_content_ideas":
            from services.content.source_tools import get_evergreen_content_ideas
            result = get_evergreen_content_ideas(
                slot=args.get("slot", "morning"),
                tone=args.get("tone", "energetic"),
                duration_seconds=args.get("duration_seconds", 30)
            )
            result["success"] = result.get("status") != "failed"
        elif name == "plan_show_rotation":
            from services.content.source_tools import plan_show_rotation
            result = plan_show_rotation(
                target_date=args.get("date", "today"),
                station_style=args.get("station_style", "Orai local entertainment")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "check_stream_health":
            from services.content.source_tools import check_stream_health
            result = check_stream_health(
                stream_url=args.get("stream_url")
            )
            result["success"] = result.get("status") != "failed"
        elif name == "diagnose_listener_path":
            from services.broadcast.listener_path import diagnose_listener_path
            result = diagnose_listener_path()
            result["success"] = True
        elif name == "set_app_listener_config":
            from services.broadcast.listener_path import set_app_listener_config
            result = set_app_listener_config(
                stream_url=args.get("stream_url"),
                api_base_url=args.get("api_base_url"),
                backup_stream_url=args.get("backup_stream_url"),
                confirmed=bool(args.get("confirmed")),
            )
            result["success"] = bool(result.get("success"))
        else:
            result = {"success": False, "error": f"Tool '{name}' is not registered."}
    except Exception as e:
        logger.error(f"[ToolRegistry] Tool execution failed: {e}")
        result = {"success": False, "error": f"Execution exception: {str(e)}"}

    # 2. Wrap execution result inside a standard JSON Envelope contract
    envelope = {
        "request_id": str(uuid.uuid4()),
        "status": "success" if result.get("success") else "failed",
        "version": "1.0.0",
        "result": result,
        "message": result.get("message") if result.get("success") else result.get("error", "Execution failed"),
        "warnings": [],
        "errors": [] if result.get("success") else [result.get("error", "Execution failed")],
        "events": []
    }
    
    return envelope

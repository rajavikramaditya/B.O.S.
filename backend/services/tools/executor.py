import os
import sys

# Setup backend path mapping (services/tools/ → backend/)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
import services.cockpit.runtime_controller as rc
import services.safety.policy_guard as policy_guard
import services.tools.legacy_gemini_registry as tr

def format_whatsapp_status_reply() -> str:
    """Factual WhatsApp gateway status line (humanize owns owner Hinglish)."""
    wa_status, wa_details = rc.get_whatsapp_health()
    if wa_status == "Live":
        qr_present = any(wa_details.get(k) for k in ["qr", "qr_code", "qrCode", "qr_code_data"])
        auth_value = (
            wa_details.get("authenticated")
            or wa_details.get("isAuthenticated")
            or wa_details.get("ready")
            or wa_details.get("connected")
            or wa_details.get("state")
            or wa_details.get("status")
        )
        details = []
        if auth_value is not None:
            details.append(f"session/auth={auth_value}")
        if qr_present:
            details.append("qr_available=true")
        detail_text = f" ({'; '.join(details)})" if details else ""
        return f"WhatsApp gateway status=Live{detail_text}."

    error = wa_details.get("error", "status unknown")
    return f"WhatsApp gateway status=Offline; local_check={error}."

def run_diagnostics_command() -> tuple[bool, str]:
    """
    Runs read-only diagnostics via the tool registry.
    Returns: (allowed: bool, result_text: str)
    """
    guard = policy_guard.check_permission("owner", "run_diagnostics")
    if not guard["allowed"]:
        return False, f"Diagnostics blocked: {guard['message']}"

    tool_res = tr.dispatch_tool_call("run_diagnostics", {})
    result = tool_res.get("result", {})
    
    log_lines = result.get("diagnostics_log", [])
    message = result.get("message", "No diagnostics message returned.")
    
    formatted_log = "\n".join(f"- {line}" for line in log_lines)
    reply_text = (
        f"Diagnostics completed:\n"
        f"{formatted_log}\n\n"
        f"Summary: {message}"
    )
    return True, reply_text

def format_center_status_reply() -> str:
    """Compiles system uptime, WhatsApp health, AzuraCast Icecast client reachable state, and local machine resource diagnostics."""
    uptime = rc.get_uptime()
    wa_status, _ = rc.get_whatsapp_health()
    stream_status = "unknown (live unverified)"
    try:
        from services.broadcast.azuracast_client import get_azuracast_status
        azura = get_azuracast_status()
        if azura.get("stream_reachable"):
            stream_status = "Online (Live unverified)"
        else:
            stream_status = "Offline/Unreachable (Live unverified)"
    except Exception:
        pass
        
    reply = (
        "Station Status:\n"
        f"- Command Center: Active (Uptime: {uptime})\n"
        f"- WhatsApp Link: {wa_status} (Local check)\n"
        f"- Playout Stream: {stream_status}\n"
        "- System Resources: Local CPU/RAM only (VM unverified in local mode)"
    )
    return reply

def format_schedule_reply() -> str:
    """Legacy SQLite schedule formatter — prefer get_station_schedule (Azura truth)."""
    schedule = db.get_playout_schedule()
    if not schedule:
        return "Playout schedule empty (sqlite_grid). Prefer AzuraCast schedule tool."
    lines = ["Playout schedule (sqlite_grid — not live Azura truth):"]
    for s in schedule:
        desc = f" ({s['description']})" if s.get("description") else ""
        lines.append(f"- {s['time_slot']}: {s['program_name']}{desc}")
    return "\n".join(lines)

def format_source_tools_status() -> str:
    """Return formatted source tool readiness summary without fake data."""
    from services.content.source_tools import get_source_tool_readiness

    readiness = get_source_tool_readiness()
    lines = ["Source tools readiness report:"]
    for tool in readiness.get("tools", []):
        status = tool.get("status", "unknown")
        truth = tool.get("truth_level", "unknown")
        configured = "yes" if tool.get("real_source_configured") else "no"
        fallback = "yes" if tool.get("fallback_available") else "no"
        blocked = tool.get("blocked_by") or "—"
        icon = "OK" if status == "success" else ("WARN" if status in ("unavailable", "manual_required") else "FAIL")
        lines.append(
            f"{icon} {tool.get('label', tool.get('tool_name'))}: "
            f"{status} | truth={truth} | real_src={configured} | fallback={fallback}"
            + (f" | blocked: {blocked}" if blocked != "—" else "")
        )

    lines.append("")
    lines.append("Unavailable tools need real API config or manual input. No fake data.")
    return "\n".join(lines)

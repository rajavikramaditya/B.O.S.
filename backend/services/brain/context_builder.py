import os
import sys
from datetime import datetime

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
import services.cockpit.runtime_controller as rc

def build_context_block() -> str:
    """
    Compiles real-time station metrics, registries, and market rates.
    """
    runtime_mode = os.environ.get("RUNTIME_MODE", "")
    is_vm = "vm" in runtime_mode.lower() and sys.platform != "win32"
    mode_str = "VM_LIVE_MODE" if is_vm else "LOCAL_TEST_MODE"

    # 1. Fetch AzuraCast Status
    try:
        from services.broadcast.azuracast_client import get_azuracast_status
        azura = get_azuracast_status()
    except Exception:
        azura = {"stream_reachable": False, "icecast_status": "offline", "autodj_status": "offline"}
    
    # 2. Fetch Service Registry
    try:
        services = db.get_service_registry()
        services_str = "\n".join([
            f"- {s['display_name']} ({s['service_name']}): status={s['last_status']}"
            for s in services
        ])
    except Exception:
        services_str = "- Services: Unavailable"
        
    # 3. Fetch Market Rates
    try:
        rates = db.get_market_rates()
        rates_str = "\n".join([
            f"- {r['item_name']}: ₹{r['price']} per unit/10g ({r['trend']}, change {r['price_change']})"
            for r in rates
        ])
    except Exception:
        rates_str = "- Rates: Unavailable"
    
    # 4. Fetch System Telemetry
    stats = rc.get_system_stats()
    uptime = rc.get_uptime()
    
    # 5. Fetch Local News headlines
    try:
        from services.content.local_news_scraper import fetch_local_news
        news_headlines = fetch_local_news()
        news_str = "\n".join([f"- Headline: {h}" for h in news_headlines])
    except Exception:
        news_str = "- News: Unavailable"
        
    # 6. Fetch Pending Song Dedications (Apna Gaana)
    try:
        dedications = db.get_pending_dedications(limit=5)
        if dedications:
            dedications_str = "\n".join([
                f"- Dedication ID {d['id']}: Listener '{d['listener_name']}' from '{d['region']}' dedicated song '{d['song_title']}' to '{d['dedicated_to']}' (Message: {d['message']})"
                for d in dedications
            ])
        else:
            dedications_str = "- Dedications: No pending requests."
    except Exception:
        dedications_str = "- Dedications: Unavailable"
    
    # Customized telemetry labels based on active runtime mode
    if not is_vm:
        stream_verification_note = "Checked locally (Simulated or verified from local machine check)"
        vm_telemetry_label = "Local Machine Telemetry (NOT GCP VM)"
    else:
        stream_verification_note = "Verified live on GCP Cloud VM"
        vm_telemetry_label = "GCP Compute VM Telemetry"

    context = f"""
ORAI RADIO COMMAND CENTER TELEMETRY & LIVE STATE:
- Runtime Mode: {mode_str} ({'Sir is running this locally. Live GCP VM status is NOT checked/verified.' if not is_vm else 'GCP Cloud VM operations verified live.'})
- Current Time: {datetime.now().strftime("%Y-%m-%d %I:%M %p")}
- {vm_telemetry_label} Load: CPU={stats.get('cpu', 0)}%, RAM={stats.get('ram', 0)}%, Uptime={uptime}
- AzuraCast Server Status ({stream_verification_note}): Reachable={azura.get('stream_reachable', False)}, Icecast={azura.get('icecast_status', 'unknown')}, AutoDJ={azura.get('autodj_status', 'unknown')}, Listeners={azura.get('listener_count', 0)}
- Currently Playing on Stream: '{azura.get('now_playing_title', 'Unknown')}' by {azura.get('now_playing_artist', 'Unknown')}
- Public stream URL: {azura.get('stream_url', 'Unconfigured')}
- Active Core Services:
{services_str}
- Current Orai Market Rates (Mandi & Sarafa):
{rates_str}
- Recent Hindi headlines from Orai/Jalaun region:
{news_str}
- Pending Listener Song Dedications (Announce these on-air in your script segments!):
{dedications_str}
"""
    return context

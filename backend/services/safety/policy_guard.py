import logging

logger = logging.getLogger(__name__)

class PolicyViolationException(Exception):
    pass

# Classify actions by permission tiers
Tiers = {
    # LEVEL 1: Read-Only
    "read-only": [
        "check_status",
        "get_playout_schedule",
        "get_leads",
        "get_requests",
        "get_voice_personas",
        "get_voice_usage",
        "run_diagnostics",
        "diagnose_listener_path",
        "get_app_listener_config",
    ],
    # LEVEL 2: Safe-Write
    "safe-write": ["add_schedule_slot", "clear_playout_schedule", "update_market_rates", "draft_script", "create_voice_preview"],
    # LEVEL 3: Requires Owner Confirmation
    "confirm-required": [
        "restart_service",
        "stop_stream",
        "publish_announcement",
        "approve_audio",
        "generate_paid_audio",
        "scrape_actor_voice",
        "set_app_listener_config",
    ],
    # LEVEL 4: Forbidden
    "forbidden": ["run_bash", "edit_env", "modify_app_files", "reveal_secrets"]
}

def check_permission(actor_role: str, action_name: str, has_confirmation: bool = False) -> dict:
    """
    Validates permissions for target actions against the actor role.
    Returns a status dict: {"allowed": bool, "requires_confirmation": bool, "message": str}
    """
    # 1. Immediate check for Forbidden (Level 4)
    if action_name in Tiers["forbidden"] or "bash" in action_name or "exec" in action_name:
        return {
            "allowed": False,
            "requires_confirmation": False,
            "message": "Action is strictly forbidden due to system safety regulations."
        }

    # 2. Customers are restricted to public safe reads and submits (no commands)
    if actor_role != "owner":
        # Public submissions like dedicaions or inquiries are allowed as safe-write if scoped
        if action_name in ["submit_dedication", "submit_lead_inquiry"]:
            return {"allowed": True, "requires_confirmation": False, "message": "Public request logged."}
        return {
            "allowed": False,
            "requires_confirmation": False,
            "message": "Access Denied. Only the Station Owner (Sir) can execute this action."
        }

    # 3. Level 3 checks (Requires confirmation)
    if action_name in Tiers["confirm-required"]:
        if has_confirmation:
            return {
                "allowed": True,
                "requires_confirmation": False,
                "message": f"Action '{action_name}' approved and authorized."
            }
        else:
            return {
                "allowed": False,
                "requires_confirmation": True,
                "message": f"Action '{action_name}' requires explicit verification from the owner."
            }

    # 4. Level 1 & 2 are safe for the owner
    if action_name in Tiers["read-only"] or action_name in Tiers["safe-write"]:
        return {
            "allowed": True,
            "requires_confirmation": False,
            "message": "Authorized."
        }

    # Default fallback
    return {
        "allowed": False,
        "requires_confirmation": True,
        "message": f"Action '{action_name}' is unclassified and requires confirmation."
    }

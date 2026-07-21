import logging

logger = logging.getLogger(__name__)

# Backend allowlist of safe tools that generic approval is allowed to run
SAFE_TOOL_ALLOWLIST = {
    "diagnostics",
    "status",
    "source_tools_status",
    "approval_queue_read",
    "schedule_read",
    "stream_status",
    "whatsapp_status"
}

# Actions that must always be blocked by backend policy
PROTECTED_ACTIONS = {
    "vm_restart",
    "deployment",
    ".env_edit",
    "db_schema_change",
    "mobile_app_changes",
    "arbitrary_shell",
    "live_ops_restart",
    "stream_server_restart",
    "production_broadcast_changes"
}

def evaluate_policy(action_packet: dict, pending_action: dict or None, msg_lower: str = "") -> dict:
    """
    Evaluates the Manager Action Packet and pending action state against backend safety policy.
    Returns:
        {
            "policy_decision": str,        # "allow_safe_tool" | "block_protected" | "clarify_approval" | "noop_chat" | "save_short_term_correction" | "manager_response_no_tool" | "tool_suggested_not_executed" | "code_audit_required"
            "action_type": str or None,
            "action_category": str or None,
            "executable_now": bool,
            "blocked_reason": str or None,
            "safe_available_tools": list,
            "required_stage": str or None,
            "tool_result": any,
            "memory_save_status": str or None,
            "response_goal": str,           # Instruction/guideline for Gemini Turn 2
            "approval_consumed": bool,
            "executable_tool": str or None,
            "response_category": str
        }
    """
    intent = action_packet.get("intent")
    route_type = action_packet.get("route_type")
    tool = action_packet.get("tool")
    
    # Base structure with clean defaults
    result = {
        "policy_decision": "manager_response_no_tool",
        "action_type": None,
        "action_category": None,
        "executable_now": True,
        "blocked_reason": "no_tool_needed",
        "safe_available_tools": list(SAFE_TOOL_ALLOWLIST),
        "required_stage": "none",
        "tool_result": None,
        "memory_save_status": None,
        "response_goal": "Speak normally in your Hinglish manager persona to help the user.",
        "approval_consumed": False,
        "executable_tool": None,
        "response_category": "chat"
    }

    # 0a. Check for model/context-identified code/file introspection questions.
    # Keep this model-first: do not infer from owner phrase lists here.
    code_audit_markers = {"code_audit", "file_inspection", "code_introspection"}
    if (
        intent in code_audit_markers
        or route_type in code_audit_markers
        or tool in code_audit_markers
        or action_packet.get("response_category") in code_audit_markers
    ):
        result.update({
            "policy_decision": "code_audit_required",
            "action_type": "code_audit",
            "action_category": "station_status",
            "response_category": "code_audit",
            "response_goal": (
                "Use the Evidence + Relevance Contract for this code-audit answer. "
                "Separate what was VERIFIED_THIS_TURN from LAST_KNOWN_PROJECT_CONTEXT and NOT_CHECKED_THIS_TURN. "
                "Say the code file was not inspected in this turn, so exact line counts/current remaining sections need a read-only code audit or owner-provided audit report. "
                "If useful, cautiously mention known project checkpoint: R4-A extraction complete and trace/tool gating bugfix testing active. "
                "If the owner asks for next extraction/refactor, do not name a specific module/task unless current audit evidence or last-known project context supports it. "
                "Without that evidence, the relevant next action is to run/provide a read-only audit."
            )
        })
        return result

    # 0b. Check if the intent is capability_report
    if intent == "capability_report":
        result.update({
            "policy_decision": "noop_chat",
            "action_type": "capability_report",
            "action_category": "station_status",
            "response_category": "capability_report",
            "response_goal": "Speak in your Hinglish manager persona. Summarize the capabilities truthfully from the Backend Capability Manifest context. Explain each capability category mode and truth level truthfully, highlighting that VM operations are strictly blocked in local mode. Permanent memory read uses PostgreSQL/pgvector with SQLite fallback when needed."
        })
        return result

    # 1. Check if the intent is a correction/rule/style preference
    if intent == "owner_correction" or route_type == "owner_correction":
        result.update({
            "policy_decision": "save_short_term_correction",
            "action_type": "save_correction",
            "action_category": "memory",
            "memory_save_status": "short_term_saved",
            "response_category": "owner_correction",
            "response_goal": "Confirm naturally in Hinglish that the correction/preference is noted in short-term state. Do not claim permanent save unless owner explicitly requested permanent memory and approved it. Do not mention old Stage M1 blocked wording."
        })
        return result

    # 1b. Creative generation is handled by the response composer LLM, not by a
    # backend tool execution. Keep safe-tool gating focused on actual tools.
    if (
        route_type == "creative_generation"
        or intent in ("creative_script", "creative_plan")
        or action_packet.get("is_creative", False)
    ):
        result.update({
            "policy_decision": "manager_response_no_tool",
            "action_type": intent or "creative_generation",
            "action_category": "creative",
            "blocked_reason": "no_tool_needed",
            "response_category": "creative_generation",
            "response_goal": (
                "Generate the requested radio creative content directly in Neena's Hinglish manager voice. "
                "Use Active Memory and State Context when relevant, especially saved style/tone preferences. "
                "For scripts, wrap the generated script inside [SCRIPT_OUTPUT] and [/SCRIPT_OUTPUT]."
            )
        })
        return result

    # 2. Check if the owner's message is classified as an approval/follow-up
    is_approval = action_packet.get("is_approval", False) or action_packet.get("is_followup", False)
    if intent in ("approval", "followup_approval"):
        is_approval = True
        
    if is_approval:
        if not pending_action:
            from services.llm.intent_router import is_confirmation_only, CONFIRMATION_ONLY_PHRASES
            words = set(msg_lower.split())
            is_real_approval_msg = (
                is_confirmation_only(msg_lower)
                or any(k in words for k in CONFIRMATION_ONLY_PHRASES)
                or any(k in words for k in ["approved", "permission", "agree"])
                or "theek hai" in msg_lower
                or "thik hai" in msg_lower
                or "permission granted" in msg_lower
            )
            if is_real_approval_msg:
                result.update({
                    "policy_decision": "clarify_approval",
                    "blocked_reason": "no_active_pending_action",
                    "response_category": "no_pending_action",
                    "response_goal": "Politely ask the owner to clarify which specific action they are approving, since there is no pending action active in the system context."
                })
            else:
                # Normal chat turn misclassified as approval/follow-up
                if tool and tool != "None":
                    result.update({
                        "policy_decision": "tool_suggested_not_executed",
                        "blocked_reason": "tool_not_executed",
                        "response_category": "chat",
                        "response_goal": f"Speak normally in your Hinglish persona. Note that tool '{tool}' was suggested by classifier but was not executed by policy."
                    })
                else:
                    result.update({
                        "policy_decision": "manager_response_no_tool",
                        "blocked_reason": "no_tool_needed",
                        "response_category": "chat",
                        "response_goal": "Speak normally in your Hinglish manager persona to help the user."
                    })
            return result
        
        action_type = pending_action.get("action_type")
        protected = pending_action.get("protected", False)
        executable_now = pending_action.get("executable_now", False)
        allowed_tool = pending_action.get("allowed_tool")
        category = pending_action.get("category", "general")
        stage_req = pending_action.get("requires_stage", "none")
        
        result.update({
            "action_type": action_type,
            "action_category": category,
            "required_stage": stage_req,
            "executable_now": executable_now and not protected
        })
        
        if protected or action_type in PROTECTED_ACTIONS:
            result.update({
                "policy_decision": "block_protected",
                "blocked_reason": f"{action_type}_blocked_local_first",
                "response_category": f"{action_type}_blocked",
                "response_goal": f"Politely explain in Hinglish that the approved action '{action_type}' is a protected VM/deployment action and is strictly blocked in local test mode (requires Stage {stage_req} verification)."
            })
            return result
            
        if not executable_now:
            result.update({
                "policy_decision": "block_protected",
                "blocked_reason": "action_not_executable_now",
                "response_category": f"{action_type}_not_executable",
                "response_goal": f"Explain that the action '{action_type}' is currently not in an executable state."
            })
            return result
            
        if allowed_tool not in SAFE_TOOL_ALLOWLIST:
            result.update({
                "policy_decision": "block_protected",
                "blocked_reason": "tool_not_in_allowlist",
                "response_category": f"tool_{allowed_tool}_blocked",
                "response_goal": f"Explain that the tool '{allowed_tool}' requested for approval is not in the backend safe allowlist."
            })
            return result
            
        # If we passed all checks, it's safe to consume/execute
        result.update({
            "policy_decision": "allow_safe_tool",
            "approval_consumed": True,
            "executable_tool": allowed_tool,
            "response_category": "allow_safe_tool",
            "response_goal": f"Acknowledge the owner's approval and report the successful execution of safe tool '{allowed_tool}'."
        })
        return result

    # 3. Check if the current action packet requests a protected action directly
    requested_protected = action_packet.get("protected_action_requested")
    
    if requested_protected in PROTECTED_ACTIONS or tool in PROTECTED_ACTIONS or action_packet.get("is_live_ops", False) or intent == "live_stream_issue":
        action_name = requested_protected or tool or "vm_restart"
        stage_req = "controlled_vm_ops"
        category = "live_ops"
        if action_name == "db_schema_change":
            stage_req = "stage_m1_memory_schema"
            category = "memory"
        elif action_name == "deployment":
            stage_req = "controlled_deployment"
            category = "deployment"
            
        result.update({
            "policy_decision": "block_protected",
            "action_type": action_name,
            "action_category": category,
            "executable_now": False,
            "required_stage": stage_req,
            "blocked_reason": f"{action_name}_blocked_local_first",
            "response_category": f"{action_name}_blocked",
            "response_goal": f"Explain in a helpful Hinglish manager tone that the request '{action_name}' is protected and has been blocked in local test mode (requires Stage {stage_req} approval). Advise that read-only status checks are available."
        })
        return result

    # 4. If it's a safe tool action, allow it
    if route_type == "tool_action" and tool in SAFE_TOOL_ALLOWLIST:
        result.update({
            "policy_decision": "allow_safe_tool",
            "executable_tool": tool,
            "response_category": "allow_safe_tool",
            "response_goal": f"Execute safe tool '{tool}' and summarize the status details to the owner."
        })
        return result

    # 5. Clean default for tool suggested but not executed
    if tool and tool != "None":
        result.update({
            "policy_decision": "tool_suggested_not_executed",
            "blocked_reason": "tool_not_executed",
            "response_category": "chat",
            "response_goal": f"Speak normally in your Hinglish persona. Note that tool '{tool}' was suggested by classifier but was not executed by policy."
        })
        return result

    # Default to general chat
    return result

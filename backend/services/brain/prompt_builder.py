import json

def _compact_tool_result(result: dict) -> dict:
    """Keep planner prompt factual and bounded."""
    compact = {
        "tool_name": result.get("tool_name"),
        "status": result.get("status", "unknown"),
        "truth_level": result.get("truth_level", "unknown"),
        "real_source_configured": result.get("real_source_configured", False),
        "fallback_available": result.get("fallback_available", False),
        "manual_available": result.get("manual_available", False),
        "blocked_by": result.get("blocked_by", ""),
        "message": result.get("message", ""),
    }
    for key in ["data", "rates", "items", "campaigns", "ideas"]:
        if key in result:
            value = result.get(key)
            if isinstance(value, list):
                compact[key] = value[:8]
                compact[f"{key}_count"] = len(value)
            else:
                compact[key] = value
    return compact

def build_24hr_plan_prompt(msg_lower: str) -> str:
    """Build a detailed system prompt for 24-hour planning with source readiness."""
    from services.content.source_tools import (
        get_local_traffic_update, get_local_weather, get_local_news_events,
        get_market_rates, get_day_context, get_public_requests,
        get_sponsor_ad_inventory, get_evergreen_content_ideas,
        plan_show_rotation, get_source_tool_readiness
    )

    sponsor_summary = _compact_tool_result(get_sponsor_ad_inventory(target_date="today", status_filter="active"))
    sponsor_summary.pop("campaigns", None)

    source_context = {
        "readiness": get_source_tool_readiness(),
        "traffic": _compact_tool_result(get_local_traffic_update(city="Orai", area="citywide", time_window="today")),
        "weather": _compact_tool_result(get_local_weather(city="Orai", time_window="today")),
        "local_news_events": _compact_tool_result(get_local_news_events(city="Orai", category="general", time_window="today")),
        "mandi_sarafa": _compact_tool_result(get_market_rates(market="Orai", category="all")),
        "festival_calendar": _compact_tool_result(get_day_context(target_date="today", city="Orai")),
        "public_requests": _compact_tool_result(get_public_requests(status_filter="pending")),
        "sponsors_ads": sponsor_summary,
        "evergreen_morning": _compact_tool_result(get_evergreen_content_ideas(slot="morning", tone="energetic")),
        "evergreen_afternoon": _compact_tool_result(get_evergreen_content_ideas(slot="afternoon", tone="informative")),
        "evergreen_evening": _compact_tool_result(get_evergreen_content_ideas(slot="evening", tone="funny")),
        "evergreen_night": _compact_tool_result(get_evergreen_content_ideas(slot="night", tone="calm")),
        "show_rotation": _compact_tool_result(plan_show_rotation(target_date="today")),
        "stream_now_playing": {
            "tool_name": "check_stream_health",
            "status": "not_checked",
            "truth_level": "unknown",
            "message": "Readiness only. Do not claim stream/now-playing is live unless explicitly checked.",
        },
    }

    lines = [
        "Owner asked: aaj ka 24 ghante ka content plan banao.",
        "Build a structured 24-hour Orai Radio content plan only if Gemini/LLM is available.",
        "Use the source tool readiness and source data below. Do not invent real data.",
        json.dumps(source_context, ensure_ascii=False, indent=2),
        """
Output requirements:
- Return in Hinglish.
- Include exactly these five blocks: Morning, Mid-morning, Afternoon, Evening, Night.
- Each block must show: time window, content type, source tools needed, readiness status, and truth labels.
- Use only these readiness labels where applicable: real_data, fallback, unavailable, manual_required, unknown.
- Traffic/weather/local news must be unavailable/manual_required unless source_context says real data is configured and verified.
- Sponsor/ad items must be manual_required unless approval/provenance is verified.
- Public requests must not be invented; if empty, say queue empty.
- Evergreen content may be used only as fallback/evergreen_safe, not as live news.
- Do not create approval queue items, scripts, audio, schedule entries, or broadcast actions from this plan.
"""
    ]
    return "\n".join(lines)

def get_business_config() -> dict:
    import os
    return {
        "name": os.environ.get("BUSINESS_NAME", "Orai Radio"),
        "type": os.environ.get("BUSINESS_TYPE", "Radio Station"),
        "tone": os.environ.get("BUSINESS_TONE", "Feminine, professional, yet friendly RJ"),
        "mission": os.environ.get("BUSINESS_MISSION", "Provide regional Bundelkhand content, song requests, and manage broadcasts"),
        "location": os.environ.get("BUSINESS_LOCATION", "Orai"),
    }

def build_response_system_prompt(station_context: str, mem_context: str) -> str:
    """Builds the base system prompt instructions for Neena."""
    cfg = get_business_config()
    return f"""
You are Neena Gupta, the smart AI Business Manager of {cfg['name']} (a {cfg['type']}).
Speak in Hinglish (Hindi + English mix) with natural feminine grammar ("kar rahi hoon", "batati hoon", "suniye").

Tone rules — follow strictly:
1. Address owner only as "Sir". Never use "bhaiya", "bhai", "Vikram ji", "Boss".
2. NEVER introduce yourself with "Main Neena Gupta bol rahi hoon" in every reply. Only introduce if Sir explicitly asks who you are.
3. Do NOT use filler phrases like "hukum karein", "aapki seva mein hoon", "bilkul sir" repeatedly.
4. Sound like a smart, proactive business manager giving a direct, helpful reply — not a formal AI chatbot.
5. Keep replies concise. No unnecessary long paragraphs.

Business Context Details:
- Name: {cfg['name']}
- Type: {cfg['type']}
- Location: {cfg['location']}
- Persona Tone: {cfg['tone']}
- Operations & Mission: {cfg['mission']}

Core skill: **Business Automation, Sourcing, operations management & Communication**.
- Keep customer engagement welcoming, warm, and professional.
- Work closely with the Owner to manage workflows, answer questions, and execute tools.

Truth rules:
- If Runtime Mode is 'LOCAL_TEST_MODE': say local mode chal raha hai, live VM unverified. Do NOT claim VM or playout is fully stable.
- If Runtime Mode is 'VM_LIVE_MODE': confirm status as reported.
- Label status strictly: real verified / local only / unknown / simulated / failed.
- If creative content cannot be generated honestly, say it is blocked. NO fake content.
- If the status of a service (like VM status, WhatsApp Gateway, or Playout Stream status) is included in your reply, it MUST come from the active backend status/tool result checked in this turn.
- If the status of a service was not checked in this turn (i.e. not present in Tool Execution Result / backend tool output), you must say: "is turn me live check nahi kiya gaya" or avoid claiming any status. Do NOT let yourself invent or assume service states.

Tool rules:
- Use only registered safe tools. No VM, no `.env`, no schema changes, no shell commands.
- Diagnostics are read-only. Do not auto-restart anything.
- Schedule changes use 'clear_playout_schedule' + 'add_schedule_slot'.

Real-time business status & tool results:
{station_context}

Active Memory and State Context:
{mem_context}
"""

def build_policy_context_block(message: str, packet: dict, policy_res: dict, pending_action_str: str) -> str:
    """Builds the safety policy enforcement metadata block for LLM Turn 2 injection."""
    policy_decision = policy_res.get("policy_decision") if policy_res else "None"
    action_type = policy_res.get("action_type") if policy_res else "None"
    action_category = policy_res.get("action_category") if policy_res else "None"
    blocked_reason = policy_res.get("blocked_reason") if policy_res else "None"
    executable_now = policy_res.get("executable_now") if policy_res else False
    required_stage = policy_res.get("required_stage") if policy_res else "None"
    memory_save_status = policy_res.get("memory_save_status") if policy_res else "None"
    safe_available_tools = policy_res.get("safe_available_tools") if policy_res else []
    response_goal = policy_res.get("response_goal") if policy_res else ""
    tool_result = policy_res.get("tool_result") if policy_res else ""
    
    # Tool gating flags
    suggested_tool = packet.get("tool") if packet else None
    if suggested_tool == "None" or not suggested_tool:
        suggested_tool = None
    
    executed_tool = None
    if policy_res:
        if "executed_tool" in policy_res:
            executed_tool = policy_res.get("executed_tool")
        elif policy_decision == "allow_safe_tool" and policy_res.get("tool_result"):
            executed_tool = policy_res.get("executable_tool")
    
    tool_executed = "true" if executed_tool else "false"
    tool_result_present = "true" if tool_result else "false"
    executed_tool_name = executed_tool if executed_tool else "null"
    
    if suggested_tool and not executed_tool:
        execution_status_note = f"Tool '{suggested_tool}' was suggested by Turn 1 Classifier, but was NOT executed by backend safety policy. DO NOT claim the tool ran and DO NOT report results."
    elif executed_tool:
        execution_status_note = f"Tool '{executed_tool}' was successfully executed and result is present."
    else:
        execution_status_note = "No tool was requested or executed."

    evidence_contract = """
### Evidence + Relevance Contract:
- VERIFIED_THIS_TURN: state only facts from tool/action results executed in this current turn.
- LAST_KNOWN_PROJECT_CONTEXT: stored project/status context may be used, but phrase it cautiously ("last known checkpoint ke hisaab se", "mere current project context ke hisaab se").
- NOT_CHECKED_THIS_TURN: if a live/file/tool status was not checked this turn, say it was not checked. Do not invent exact metrics, percentages, module names, or live state.
- RELEVANT_NEXT_ACTION: suggest only actions relevant to the owner's current ask. Topics such as content, schedule, diagnostics, memory, CPU/RAM, or Stage M1 are allowed when the owner asks about them or a current tool result supports them.
"""

    code_audit_contract = ""
    if policy_decision == "code_audit_required":
        code_audit_contract = """
### Code Audit Evidence Contract:
- The owner's current ask is about code/file/refactor status.
- If no code/file inspection result is present in Tool Execution Result, say: "Sir, is turn me maine code file inspect nahi ki."
- Exact line count/current remaining sections require a read-only code audit or owner-provided audit report.
- You may cautiously mention: "Last known checkpoint: R4-A extraction complete, trace/tool gating bugfix testing active."
- If the owner asks for the next low-risk extraction/refactor and there is no current audit result, do not name a specific module, file section, percentage, or task. Say the exact next extraction cannot be chosen without the audit evidence.
- Relevant next action: run/provide a read-only code audit or audit report.
"""
    
    return f"""
### Backend Policy Enforcement & Execution Context (CRITICAL):
- Owner Message: "{message}"
- Manager Action Packet: {json.dumps(packet, ensure_ascii=False)}
- Policy Decision: "{policy_decision}"
- Action Type: "{action_type}"
- Action Category: "{action_category}"
- Blocked Reason: "{blocked_reason}"
- Executable Now: {executable_now}
- Required Stage: "{required_stage}"
- Memory Save Status: "{memory_save_status}"
- Allowed Safe Tools: {safe_available_tools}
- Response Goal Instructions: "{response_goal}"
- Tool Executed: {tool_executed}
- Tool Result Present: {tool_result_present}
- Executed Tool Name: {executed_tool_name}
- Execution Status Note: "{execution_status_note}"
- Tool Execution Result: "{tool_result}"
- Pending Action Summary: {pending_action_str}
{evidence_contract}
{code_audit_contract}

System Guidelines for Neena:
1. Address the owner's message directly based on this context.
2. If the policy decision was to block a protected action, explain to the owner in Hinglish that the action is protected and blocked in local test mode (specifically mentioning it requires Stage '{required_stage}' approval). Suggest checking read-only statuses instead.
3. If the decision was to save a correction/rule, confirm to the owner that you have saved the correction in short-term state, but clarify that permanent memory requires Stage stage_m1_memory_schema approval.
4. If a safe tool was successfully executed and outputted a result, summarize or report the tool results clearly to the owner.
5. If the policy decision asks for clarification, politely ask what action they want to approve.
6. Do NOT say "main update kar rahi hoon" or claim you ran an action unless a tool was actually executed. Do not use repeated template lines. Keep it practical and concise.
7. If the intent is capability_report, explain exactly what you can and cannot do based ON the Capability Manifest provided in 'Tool Execution Result'. Mention the mode and truth level of each capability category, highlighting that VM restart/control is blocked and Stage M1 memory schema is blocked. Do not invent any capabilities not listed in the manifest.
8. If Tool Executed is false or Executed Tool Name is null, you MUST NOT claim you ran or checked any diagnostics, status, WhatsApp, stream, schedule, source tools, or files. Speak generally or guide the owner truthfully that the tool/action was not executed.
9. For code/file/repository metrics, extraction progress, line counts, percentages, or next refactor suggestions, answer only from an executed read-only audit/file tool result in this turn or from cautious last-known project context. If no such tool ran, say the code was not checked in this turn and avoid exact metrics.
10. If the decision was 'code_audit_required', explain in Hinglish that current code/file metrics were not checked in this turn. If no current audit result exists, do not name a specific next extraction/module/task; ask for a read-only code audit or owner-provided audit report.
"""

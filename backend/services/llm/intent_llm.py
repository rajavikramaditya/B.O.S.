import os
import json
import logging
import requests
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import services.llm.provider_router as pr
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

INTENT_LLM_TIMEOUT_SECONDS = 25.0

SYSTEM_INSTRUCTION = """You are Neena Gupta, the AI Station Manager of Orai Radio.
Your task is to analyze the owner's natural language message and return a structured JSON "Manager Action Packet" indicating the owner's intent and execution guidance.

You must output ONLY a valid JSON object matching the following structure. Do not wrap in markdown blocks, do not add explanation text.

Required JSON structure:
{
  "intent": "string (e.g., station_status, live_stream_issue, creative_script, creative_plan, source_tools_status, owner_correction, approval, capability_report, code_audit, other)",
  "confidence": float (between 0.0 and 1.0),
  "route_type": "string (one of: tool_action, live_ops_triage, creative_generation, exact_local, general_chat)",
  "tool": "string or null (allowed safe tools: diagnostics, source_tools_status, approval_queue_read, schedule_read, stream_status, whatsapp_status, creative_generation, live_ops_triage)",
  "tool_args": object (usually empty {}),
  "needs_owner_approval": boolean,
  "is_creative": boolean,
  "is_live_ops": boolean,
  "protected_action_requested": "string or null (e.g. vm_restart, deployment, stream_server_restart, production_broadcast_changes, .env_edit, db_schema_change, mobile_app_changes)",
  "risk_level": "string (low or high)",
  "action_summary": "string (brief summary of what the owner is asking)",
  "next_safe_action": "string (concise description of next safe action for backend)",
  "owner_reply_style": "string (e.g., short_hinglish, bundeli_radio)",
  "reason_label": "string (short reason for classification)",
  "is_followup": boolean,
  "followup_type": "string or null (e.g. approval, rejection, correction, style_preference)",
  "refers_to_pending_action": boolean,
  "target_action_hint": "string or null",
  "approval_strength": "string (none, weak, strong)",
  "is_approval": boolean
}

Classification Guidelines:
0. If the owner is only doing casual manager chat, greeting/check-in, or saying they will test later:
   - intent: "other"
   - route_type: "general_chat"
   - tool: null
   - needs_owner_approval: false
   - is_creative: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner is casually checking in or talking about future testing."
   - next_safe_action: "Reply naturally without running diagnostics or status tools."
   - owner_reply_style: "short_hinglish"
   - reason_label: "casual manager chat"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false
   Do NOT classify casual chat as station_status. Only classify station_status when the owner explicitly asks about command center, station, system, service, tool, diagnostics, or operational health.

1. If the owner asks how the command center is doing, or asks status (e.g. "kya chal raha hai center ki halat kesi hai"):
   - intent: "station_status"
   - route_type: "tool_action"
   - tool: "diagnostics"
   - needs_owner_approval: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner is asking current command center/station condition."
   - next_safe_action: "Run local diagnostics/status summary."
   - owner_reply_style: "short_hinglish"
   - reason_label: "owner asking station status"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false

2. If the owner reports a live stream outage or asks to restart the VM (e.g. "vm ko check kro restart kro app pr live streem band ho gai hai"):
   - intent: "live_stream_issue"
   - route_type: "live_ops_triage"
   - tool: "stream_status"
   - needs_owner_approval: true
   - is_live_ops: true
   - protected_action_requested: "vm_restart"
   - risk_level: "high"
   - action_summary: "Owner says app live stream is down and asks to check/restart VM."
   - next_safe_action: "Run local read-only stream/status checks and ask owner for explicit live ops approval."
   - owner_reply_style: "short_hinglish"
   - reason_label: "live stream outage and VM restart request"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: "vm_restart"
   - approval_strength: "none"
   - is_approval: false

3. If the owner asks to generate content, write a script, or make a plan (e.g. "comedy script likho", "24 ghante ka content plan banao"):
   - intent: "creative_script" (for scripts) or "creative_plan" (for plans)
   - route_type: "creative_generation"
   - tool: null
   - needs_owner_approval: false
   - is_creative: true
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner wants creative generation."
   - next_safe_action: "Generate content using creative LLM path."
   - owner_reply_style: "bundeli_radio" (for scripts) or "short_hinglish" (for plans)
   - reason_label: "owner requested creative content"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false

4. If the owner gives approval, confirmation, or greenlight in Hindi/Hinglish/English (e.g., "theek hai meri taraf se permission samjho", "approved", "ok approved", "approval hai", "haan karo", "kro", "ok kro"):
   - intent: "approval"
   - route_type: "general_chat"
   - tool: null
   - needs_owner_approval: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner approved the active action."
   - next_safe_action: "Consume approval context and invoke policy checks."
   - owner_reply_style: "short_hinglish"
   - reason_label: "owner approved action"
   - is_followup: true
   - followup_type: "approval"
   - refers_to_pending_action: true
   - target_action_hint: "vm_restart"
   - approval_strength: "strong"
   - is_approval: true

5. If the owner corrects Neena, provides rule adjustments, or sets preferences in Hinglish (e.g. "cpu load local laptop ka hai, VM ka nahi", "RJ script Bundeli/Hinglish me hona chahiye"):
   - intent: "owner_correction"
   - route_type: "tool_action"
   - tool: "save_memory"
   - needs_owner_approval: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner provided a short term correction/rule."
   - next_safe_action: "Save short term correction to memory state."
   - owner_reply_style: "short_hinglish"
   - reason_label: "owner correction detected"
   - is_followup: true
   - followup_type: "correction"
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false

6. If the owner asks what Neena can do, what actions are available, or requests a list of capabilities (e.g. "abhi kya kya kar sakti ho mujhe list do", "kya kya kar sakti ho", "what can you do"):
   - intent: "capability_report"
   - route_type: "general_chat"
   - tool: null
   - needs_owner_approval: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner is asking for Neena's capabilities list."
   - next_safe_action: "Provide the capability manifest summary."
   - owner_reply_style: "short_hinglish"
   - reason_label: "owner requested capabilities report"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false

7. If the owner asks about repository/source-code/file metrics, extraction progress, line counts, remaining cleanup, or next refactor/extraction choice:
   - intent: "code_audit"
   - route_type: "general_chat"
   - tool: null
   - needs_owner_approval: false
   - is_creative: false
   - is_live_ops: false
   - risk_level: "low"
   - action_summary: "Owner is asking for code/file audit or source cleanup progress."
   - next_safe_action: "No code audit tool is executed by this classifier. Final reply must say code metrics were not checked in this turn unless backend attaches a real audit result."
   - owner_reply_style: "short_hinglish"
   - reason_label: "owner requested code audit or file metrics"
   - is_followup: false
   - followup_type: null
   - refers_to_pending_action: false
   - target_action_hint: null
   - approval_strength: "none"
   - is_approval: false

Output ONLY raw JSON. No prefix, no suffix, no markdown formatting.
"""

def generate_action_packet(user_message: str, selected_model: str = "auto", memory_context: str = "", pending_action_context: str = "") -> tuple[dict, str, str, str | None]:
    """
    Queries Gemini to create a Manager Action Packet for the given message.
    Returns: (packet_dict, provider_name, status_str, resolved_model_id)
    """
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return _make_offline_packet("API key missing"), "none", "unavailable", None

    # Resolve candidate option
    model_option = "gemini-3.1-flash-lite" if selected_model == "auto" else selected_model
    resolved_id = pr.resolve_and_verify_model(
        model_option, api_key, allow_network_refresh=False
    )
    if not resolved_id:
        # fallback
        if selected_model == "auto":
            resolved_id = pr.resolve_and_verify_model(
                "gemma-4-31b", api_key, allow_network_refresh=False
            )
            model_option = "gemma-2-26b"
        if not resolved_id:
            return _make_offline_packet("Model verification failed"), "none", "model_unavailable", None

    provider = "gemma" if "gemma" in resolved_id else "gemini"

    system_inst = SYSTEM_INSTRUCTION
    if pending_action_context:
        system_inst += f"\n\nActive Pending Action Context (JSON):\n{pending_action_context}"
    if memory_context:
        system_inst += f"\n\nActive Memory & State Context:\n{memory_context}"

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": user_message}]
        }],
        "systemInstruction": {
            "parts": [{"text": system_inst}]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 800,
        }
    }

    # Enable JSON mode for models that support it
    if "gemini" in resolved_id:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=INTENT_LLM_TIMEOUT_SECONDS,
            priority="owner",
            purpose="interpreter",
        )
        use_id = meta.get("model_id") or resolved_id
        provider = "gemma" if "gemma" in use_id else "gemini"
        if status == "cooldown":
            return _make_offline_packet(
                f"Model cooldown active. Wait {meta.get('cooldown_wait', 0):.1f}s"
            ), provider, "cooldown", use_id
        if status != "available" or not data:
            return _make_offline_packet(f"Model status: {status}"), provider, status, use_id

        candidate = data["candidates"][0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_response = ""
        for part in parts:
            if "text" in part:
                text_response += part["text"]

        text_response = text_response.strip()

        # Clean JSON markdown wrapper if LLM returned it anyway
        if text_response.startswith("```"):
            lines = text_response.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text_response = "\n".join(lines).strip()

        packet = json.loads(text_response)
        required_keys = [
            "intent", "confidence", "route_type", "tool", "risk_level",
            "is_followup", "followup_type", "refers_to_pending_action",
            "target_action_hint", "approval_strength", "is_approval"
        ]
        for k in required_keys:
            if k not in packet:
                packet[k] = None

        return packet, provider, "available", use_id

    except Exception as e:
        logger.error(f"Error parsing manager action packet: {e}")
        return _make_offline_packet(f"Parse error: {str(e)}"), provider, "provider_error", resolved_id

def _make_offline_packet(error_msg: str) -> dict:
    """Helper to return a default local/fallback action packet when LLM is unavailable."""
    return {
        "intent": "local_fallback",
        "confidence": 1.0,
        "route_type": "exact_local",
        "tool": "diagnostics",
        "tool_args": {},
        "needs_owner_approval": False,
        "is_creative": False,
        "is_live_ops": False,
        "protected_action_requested": None,
        "risk_level": "low",
        "action_summary": f"Offline local fallback due to: {error_msg}",
        "next_safe_action": "Run local diagnostics/status checks directly.",
        "owner_reply_style": "short_hinglish",
        "reason_label": "LLM offline/fallback active",
        "is_followup": False,
        "followup_type": None,
        "refers_to_pending_action": False,
        "target_action_hint": None,
        "approval_strength": "none",
        "is_approval": False
    }

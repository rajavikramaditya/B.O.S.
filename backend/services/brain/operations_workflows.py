"""M3-A1 launch operations workflows (model-routed, dynamic Gemini generation)."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import services.llm.provider_router as pr
import services.cockpit.runtime_controller as rc
from services.memory.pg_repository import LIVE_MEMORY_BACKEND, is_pgvector_available, is_postgres_available
from services.brain.operations_classifier import (
    LOW_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    classify_operations_intent,
    deterministic_fallback_intent,
)
from services.memory.production_health import get_production_memory_shadow_health
from services.brain.redis_state import LIVE_SESSION_BACKEND, is_redis_available
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT_SECONDS = 35.0


def _fallback_rj_intro_local(message: str, fields: dict) -> str:
    """Broadcast-ready local template when Gemini creative generation is unavailable."""
    msg = (message or "").lower()
    tone = (fields.get("tone") or "").lower()
    if not tone:
        if any(t in msg for t in ["funny", "comedy", "hasya"]):
            tone = "funny"
        else:
            tone = "energetic"
    show_time = fields.get("show_time") or ""
    if not show_time and any(t in msg for t in ["subah", "morning", "kal subah"]):
        show_time = "morning"
    time_phrase = "kal subah ke show" if show_time == "morning" else "aaj ke show"

    if tone == "funny":
        return (
            f"Ram ram Orai wale bhaiyon-behenon! Main hoon aapki digital dost Neena Gupta — "
            f"aur ab shuru ho raha hai {time_phrase} ka full-on hungama!\n\n"
            "Yeh hai Orai Radio — jahan gaon ki galiyon se lekar dil tak awaaz jaati hai. "
            "Aaj mood hai thoda funny, thoda filmy, poora Orai touch ke sath!\n\n"
            "Toh taiyaar ho jaiye — music, masti, aur aapke sheher ki baatein. "
            "Orai Radio pe rehna mat bhooliye — kyunki yahan signal strong hai aur mood bhi!\n\n"
            "Chalo, shuru karte hain!"
        )
    return (
        f"Namaste Orai! Main Neena Gupta, aapki AI Station Manager — {time_phrase} ke liye taiyaar hoon.\n\n"
        "Orai Radio par aapka swagat hai — yahan local touch, desi vibe, aur aapke favourite gaane milenge. "
        "Aaj ka din shandaar hone wala hai!\n\n"
        "Music shuru, mood set — Orai Radio ke sath judiye!"
    )


def _generation_model_chain(selected_model: str, *, use_creative_role: bool) -> list[str | None]:
    """Ordered API model ids to try for creative generation."""
    if use_creative_role and selected_model == "auto":
        chain: list[str | None] = []
        for role in ("CREATIVE_MODEL", "FALLBACK_MODEL"):
            mid = pr.resolve_model_for_role(role)
            if mid and mid not in chain:
                chain.append(mid)
        return chain or [None]
    model_option = "gemini-3.1-flash-lite" if selected_model == "auto" else selected_model
    resolved = pr.resolve_and_verify_model(model_option, pr.get_gemini_api_key() or "", allow_network_refresh=False)
    return [resolved] if resolved else [None]


def _apply_ops_trace(tb, packet: dict, *, intent_source: str, workflow_name: str | None, mem_packet: dict) -> None:
    tb.operation_intent = packet.get("intent")
    tb.intent_confidence = packet.get("confidence")
    tb.intent_source = intent_source
    tb.workflow_name = workflow_name
    tb.extracted_fields = packet.get("extracted_fields") or {}
    hits = int(mem_packet.get("memory_hits_count") or 0)
    tb.memory_applied = hits > 0 or bool(mem_packet.get("semantic_memory_used"))


def _script_length_policy(message: str) -> tuple[str, int]:
    """Owner length ask → prompt line + maxOutputTokens (break ~200-word wall)."""
    msg = (message or "").lower()
    if any(
        k in msg
        for k in (
            "1500",
            "1000 word",
            "1000 words",
            "bohot lamba",
            "bahut lamba",
            "full show",
            "10 min",
            "10 minute",
        )
    ):
        return (
            "LENGTH: Write a LONG script — target about 800–1500 words. Do not stop early.",
            4096,
        )
    if any(
        k in msg
        for k in (
            "lamba",
            "lambi",
            "long",
            "bada",
            "badi script",
            "600",
            "500 word",
            "5 min",
            "5 minute",
            "zyada lamba",
        )
    ):
        return (
            "LENGTH: Write a LONGER script — target about 400–800 words. Do not keep it short.",
            3072,
        )
    return (
        "LENGTH: Medium on-air length (~120–250 words) unless the owner asked for longer.",
        2048,
    )


def _generate_with_gemini(
    system_prompt: str,
    user_message: str,
    selected_model: str = "auto",
    max_tokens: int = 1400,
    *,
    use_creative_role: bool = True,
) -> tuple[str, str, str, str | None]:
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return "", "none", "unavailable", None

    model_chain = _generation_model_chain(selected_model, use_creative_role=use_creative_role)
    last_provider = "none"
    last_status = "model_unavailable"
    last_id: str | None = None

    for resolved_id in model_chain:
        if not resolved_id or pr.is_disallowed_normal_flow_model(resolved_id):
            continue
        last_id = resolved_id
        provider = "gemma" if "gemma" in resolved_id else "gemini"
        last_provider = provider
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
        }
        try:
            data, status, meta = pr.call_generate_content_json(
                resolved_id,
                api_key,
                payload,
                timeout=GENERATION_TIMEOUT_SECONDS,
                priority="background",
                purpose="creative",
            )
            use_id = meta.get("model_id") or resolved_id
            provider = "gemma" if "gemma" in use_id else "gemini"
            last_provider = provider
            last_id = use_id
            if status in ("cooldown", "rate_limited", "quota_deferred"):
                last_status = status
                continue
            if status != "available" or not data:
                last_status = "provider_error"
                continue
            text = ""
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if part.get("thought"):
                    continue
                text += part.get("text", "")
            text = text.strip()
            if text:
                return text, provider, "available", use_id
            last_status = "provider_error"
        except requests.exceptions.Timeout:
            last_status = "timeout"
        except Exception as exc:
            logger.error("Workflow generation failed (%s): %s", resolved_id, exc)
            last_status = "provider_error"

    return "", last_provider, last_status, last_id


def _memory_snippet(mem_packet: dict, mem_context: str) -> str:
    lines = []
    for hit in mem_packet.get("hits") or []:
        if hit.get("source") == "short_term":
            continue
        content = (hit.get("content") or "").strip()
        if content:
            lines.append(f"- {content}")
    if lines:
        return "Saved permanent memories relevant to this request:\n" + "\n".join(lines)
    if mem_context:
        return mem_context[:2500]
    return "No specific permanent memory hits; use general Orai Radio manager tone."


def build_station_status_reply(scope: str = "full") -> str:
    health = get_production_memory_shadow_health()
    wa = rc.get_whatsapp_gateway_trace_status()
    pg = "healthy" if health.get("postgres_available") else "unavailable"
    pgvec = "active" if health.get("pgvector_available") else "unavailable"
    redis_st = "healthy" if health.get("redis_available") else "unavailable"
    mem_read = "postgres_pgvector_primary" if health.get("pgvector_available") else "sqlite_fallback"
    session_st = LIVE_SESSION_BACKEND or "redis_primary"

    stream_line = "AzuraCast stream: offline/unreachable (local check)"
    try:
        from services.broadcast.azuracast_client import get_azuracast_status
        az = get_azuracast_status()
        if az.get("stream_reachable"):
            stream_line = (
                f"AzuraCast stream: reachable — "
                f"{az.get('now_playing_artist', 'Unknown')} - {az.get('now_playing_title', 'Unknown')}"
            )
        else:
            stream_line = "AzuraCast stream: offline/unreachable"
    except Exception:
        pass

    stats = rc.get_system_stats()
    short = scope == "short" or scope == "health_only"
    lines = [
        "Orai Radio station status (local check):",
        f"- Backend: active",
        f"- PostgreSQL: {pg}",
        f"- pgvector: {pgvec}",
        f"- Redis session: {redis_st} ({session_st})",
        f"- Memory read: {mem_read}",
        f"- Memory write: postgres_primary + sqlite_mirror",
        f"- WhatsApp gateway: {wa} (non-blocking)",
        f"- {stream_line}",
    ]
    if not short:
        lines.append(f"- Local CPU: {stats.get('cpu', '?')}%, RAM: {stats.get('ram', '?')}%")
    return "\n".join(lines)


def _workflow_station_status(packet: dict, mem_packet: dict, tb) -> dict:
    fields = packet.get("extracted_fields") or {}
    scope = (fields.get("requested_scope") or "full").lower()
    reply = build_station_status_reply(scope)
    tb.source = "local_router"
    tb.route = "station_status"
    tb.executed_tool_name = "station_status"
    tb.local_tool_executed = "station_status"
    tb.final_reply_source = "operations_workflow"
    tb.step("response", "Station status workflow completed")
    return {"reply": reply, "action_type": "STATION_STATUS"}


def _mark_generation_unavailable(tb, status: str, model_id: str | None) -> None:
    wait = pr.peek_cooldown_wait(model_id) if model_id else 0.0
    pr.apply_model_limit_trace(tb, model_call_status=status or "cooldown", wait_seconds=wait)


def _workflow_rj_intro(message: str, packet: dict, mem_packet: dict, mem_context: str, selected_model: str, tb) -> dict | None:
    fields = packet.get("extracted_fields") or {}
    memory_block = _memory_snippet(mem_packet, mem_context)
    safe_note = ""
    if float(packet.get("confidence") or 0) < MEDIUM_CONFIDENCE_THRESHOLD:
        safe_note = "Keep intro conservative; owner intent confidence is medium."

    message_lower = message.lower()
    is_local_requested = any(kw in message_lower for kw in ["weather", "mausam", "news", "samachar", "khabar", "traffic", "jam"])
    
    local_source_instruction = ""
    if is_local_requested:
        local_source_instruction = "\n- Live weather/news/traffic sources are UNAVAILABLE. Do NOT fabricate news, weather numbers, or traffic status. Omit them entirely or replace with general music/vibe greetings."

    length_rule, max_tok = _script_length_policy(message)
    system = f"""You are Neena Gupta, AI Station Manager of Orai Radio.
Write a fresh RJ intro script for live radio based on the owner request.
{safe_note}

Rules:
- Use saved permanent memories for tone/style/local Orai touch when relevant
- Bundeli/Hinglish comedy tone when memory or request says so
- Energetic, clean, non-vulgar, directly usable on air
- {length_rule}
- Do NOT use fixed templates; generate new content each time
- Do NOT mention Stage M1 or blocked memory
- Output ONLY the intro script text (no meta commentary){local_source_instruction}

{memory_block}

Owner extracted hints: {json.dumps(fields, ensure_ascii=False)}"""

    reply, provider, status, model_id = _generate_with_gemini(
        system, message, selected_model, max_tokens=max_tok
    )
    if status != "available" or not reply:
        _mark_generation_unavailable(tb, status, model_id)
        reply = _fallback_rj_intro_local(message, fields)
        tb.llm_used = False
        tb.llm_provider = "local"
        tb.llm_status = "local_template_fallback"
        tb.actual_model = None
        tb.response_composer_model_used = "local_template"
        tb.response_model_call_count = 0
        tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0)
        tb.source = "local_fallback"
        tb.route = "rj_intro"
        tb.final_reply_source = "operations_workflow_local_fallback"
        tb.step("response", f"RJ intro local template fallback (gen status={status})")
    else:
        tb.llm_used = True
        tb.llm_provider = provider
        tb.llm_status = status
        tb.actual_model = model_id
        tb.response_composer_model_used = model_id or "gemini-3.1-flash-lite"
        tb.response_model_call_count = 1
        tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0) + 1
        tb.source = f"{provider}_api"
        tb.route = "rj_intro"
        tb.final_reply_source = "operations_workflow_gemini"
        tb.step("response", "RJ intro workflow generated via Gemini")

    # Clean up placeholders programmatically and apply warnings
    if is_local_requested or "[LOCAL UPDATE PLACEHOLDER]" in reply or "[WEATHER PLACEHOLDER]" in reply:
        warning = "Live weather/news source not connected; will not invent that content.\n\n"
        if warning not in reply:
            reply = warning + reply
    reply = reply.replace("[LOCAL UPDATE PLACEHOLDER]", "").replace("[WEATHER PLACEHOLDER]", "")

    return {"reply": reply, "action_type": "RJ_INTRO"}


def _workflow_ad_script(message: str, packet: dict, mem_packet: dict, mem_context: str, selected_model: str, tb) -> dict | None:
    fields = packet.get("extracted_fields") or {}
    memory_block = _memory_snippet(mem_packet, mem_context)
    duration = fields.get("duration_seconds") or 20
    system = f"""You are Neena Gupta, AI Station Manager of Orai Radio.
Write a fresh radio advertisement script based on the owner request.

Output format (use these headings):
Title:
Duration: {duration} seconds
Voice style:
Script:
CTA:

Rules:
- Business name clearly repeated in script (at least twice if known)
- Short CTA if memory or request prefers short CTA
- Local Orai feel when requested or remembered
- Clean, non-vulgar, broadcast-ready
- Generate new content; no fixed template filler
- Do NOT auto-save or mention memory save unless owner asked

{memory_block}

Owner extracted hints: {json.dumps(fields, ensure_ascii=False)}"""

    reply, provider, status, model_id = _generate_with_gemini(system, message, selected_model, max_tokens=1600)
    if status != "available" or not reply:
        _mark_generation_unavailable(tb, status, model_id)
        return None
    tb.llm_used = True
    tb.llm_provider = provider
    tb.llm_status = status
    tb.actual_model = model_id
    tb.response_composer_model_used = model_id or "gemini-3.1-flash-lite"
    tb.response_model_call_count = 1
    tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0) + 1
    tb.source = f"{provider}_api"
    tb.route = "ad_script"
    tb.final_reply_source = "operations_workflow_gemini"
    tb.step("response", "Ad script workflow generated via Gemini")
    return {"reply": reply, "action_type": "AD_SCRIPT"}


def _workflow_daily_show_plan(message: str, packet: dict, mem_packet: dict, mem_context: str, selected_model: str, tb) -> dict | None:
    fields = packet.get("extracted_fields") or {}
    segments = fields.get("number_of_segments") or 5
    memory_block = _memory_snippet(mem_packet, mem_context)
    system = f"""You are Neena Gupta, AI Station Manager of Orai Radio.
Create a daily/morning show content plan with {segments} segments.

Include:
- Opening intro segment
- Local update (omit news/weather/traffic details if live data is unavailable; do NOT use placeholders or fabricate data. Talk about general music/vibe instead)
- Ad break placeholder
- Listener engagement line
- Closing line

Rules:
- No fake live news, market rates, or weather numbers
- Apply saved memory preferences for tone/local touch
- Hinglish manager tone in segment descriptions
- Fresh plan each time; no fixed template script

{memory_block}

Owner extracted hints: {json.dumps(fields, ensure_ascii=False)}"""

    reply, provider, status, model_id = _generate_with_gemini(system, message, selected_model, max_tokens=1600)
    if status != "available" or not reply:
        _mark_generation_unavailable(tb, status, model_id)
        return None

    # Prepend warning to response and clean up placeholders programmatically
    warning = "Live weather/news source not connected; will not invent that content.\n\n"
    if warning not in reply:
        reply = warning + reply
    reply = reply.replace("[LOCAL UPDATE PLACEHOLDER]", "").replace("[WEATHER PLACEHOLDER]", "")

    tb.llm_used = True
    tb.llm_provider = provider
    tb.llm_status = status
    tb.actual_model = model_id
    tb.response_composer_model_used = model_id or "gemini-3.1-flash-lite"
    tb.response_model_call_count = 1
    tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0) + 1
    tb.source = f"{provider}_api"
    tb.route = "daily_show_plan"
    tb.final_reply_source = "operations_workflow_gemini"
    tb.step("response", "Daily show plan workflow generated via Gemini")
    return {"reply": reply, "action_type": "DAILY_SHOW_PLAN"}


def try_handle_operations(
    message: str,
    selected_model: str,
    mem_packet: dict,
    mem_context: str,
    tb,
) -> dict | None:
    """
    Model-based operations router. Returns save_and_return payload or None to fall through.
    """
    if not pr.is_llm_configured():
        return None

    t0 = time.monotonic()
    packet, provider, status, model_id = classify_operations_intent(
        message, selected_model, memory_context=mem_context
    )
    intent_source = "gemini_classifier"
    wait_needed = pr.peek_cooldown_wait(model_id) if model_id else 0.0
    if status != "available":
        fb = deterministic_fallback_intent(message)
        if fb:
            packet = fb
            intent_source = "fallback"
        elif pr.is_model_rate_limited_status(status):
            pr.apply_model_limit_trace(tb, model_call_status=status, wait_seconds=wait_needed)
            tb.source = "local_router"
            tb.route = "model_cooldown_retry"
            tb.final_reply_source = "model_cooldown_guard"
            tb.step("response", f"Classifier blocked by {status}")
            return {
                "reply": pr.build_owner_cooldown_reply(wait_needed),
                "action_type": "MODEL_COOLDOWN_RETRY",
                "_tb": tb,
            }
        else:
            return None

    intent = packet.get("intent") or "general_chat"
    confidence = float(packet.get("confidence") or 0.0)

    # Defer to existing deterministic safety paths
    if intent in {"permanent_memory_save", "approval", "diagnostics"}:
        return None

    if intent == "general_chat":
        return None

    if intent == "clarification_needed" or confidence < LOW_CONFIDENCE_THRESHOLD:
        _apply_ops_trace(tb, packet, intent_source=intent_source, workflow_name="clarification", mem_packet=mem_packet)
        hint = (packet.get("extracted_fields") or {}).get("clarification_question_hint")
        reply = hint or "Clarify needed: station status, RJ intro, ad script, or show plan?"
        tb.source = "local_router"
        tb.route = "clarification"
        tb.step("response", "Operations classifier requested clarification")
        return {"reply": reply, "action_type": "clarification", "_tb": tb}

    tb.mark("routing")
    tb._checkpoints["routing"] = round((time.monotonic() - t0) * 1000)
    tb.intent_model_call_count = 1

    workflow_handlers = {
        "station_status": lambda: _workflow_station_status(packet, mem_packet, tb),
        "rj_intro": lambda: _workflow_rj_intro(message, packet, mem_packet, mem_context, selected_model, tb),
        "ad_script": lambda: _workflow_ad_script(message, packet, mem_packet, mem_context, selected_model, tb),
        "daily_show_plan": lambda: None,  # retired → create_station_plan hand
    }

    if intent == "daily_show_plan":
        from services.tools.catalog import ToolContext
        from services.tools.station_plan import _handle_create

        fields = packet.get("extracted_fields") or {}
        out = _handle_create(
            ToolContext(
                action="create_station_plan",
                slots={
                    "horizon": "shift_4h",
                    "theme": str(fields.get("show_type") or "")[:120],
                    "hours": fields.get("number_of_segments"),
                },
                snapshot={},
                owner_message=message,
            )
        )
        if out:
            out["_tb"] = tb
            tb.route = "create_station_plan"
            tb.final_reply_source = "station_plan"
        return out

    handler = workflow_handlers.get(intent)
    if not handler:
        return None

    _apply_ops_trace(tb, packet, intent_source=intent_source, workflow_name=intent, mem_packet=mem_packet)
    result = handler()
    if result is None and intent in {"rj_intro", "ad_script"}:
        gen_wait = pr.peek_cooldown_wait(model_id) if model_id else wait_needed
        pr.apply_model_limit_trace(tb, model_call_status="cooldown", wait_seconds=gen_wait)
        tb.route = intent
        tb.final_reply_source = "operations_workflow_retry"
        tb.step("response", f"{intent} generation unavailable (cooldown/provider)")
        return {
            "reply": pr.build_owner_cooldown_reply(gen_wait),
            "action_type": "OPERATIONS_GENERATION_RETRY",
            "_tb": tb,
        }
    if result is None:
        return None

    # M4-A1: queue broadcast scripts + create capsule (no audio, no AzuraCast).
    # daily_show_plan is NOT a capsule — living Station Clock plan owns agendas.
    if intent in {"rj_intro", "ad_script"} and result.get("reply"):
        try:
            from services.broadcast.capsule_service import (
                append_capsule_footer,
                queue_script_and_create_capsule,
            )
            script_text = result["reply"].strip()
            if script_text:
                queued = queue_script_and_create_capsule(
                    script_text,
                    intent=intent,
                    source="m3_workflow",
                    metadata={"intent_confidence": confidence},
                )
                result["reply"] = append_capsule_footer(
                    script_text,
                    queued["approval_id"],
                    queued["capsule_id"],
                )
                result["approval_id"] = queued["approval_id"]
                result["capsule_id"] = queued["capsule_id"]
                result["approval_status"] = "pending_review"
                result["audio_truth_level"] = "none"
                result["azuracast_status"] = "blocked"
                tb.step(
                    "db_write",
                    f"Queued M3 {intent} to approval {queued['approval_id']} capsule {queued['capsule_id']}",
                )
        except Exception as exc:
            logger.error("Failed to queue M3 broadcast script: %s", exc)
            result["reply"] += (
                "\n\nWarning: script generate ho gaya par approval queue/capsule save fail ho gaya. "
                "Broadcast-ready claim nahi karungi."
            )

    result["_tb"] = tb
    return result


def _apply_local_ops_trace(tb, action: str, *, manifest_meta: dict | None = None) -> None:
    tb.source = "local_router"
    tb.route = action
    tb.final_reply_source = "interpreter_local_action"
    tb.intent_model_call_count = 0
    tb.response_model_call_count = 0
    tb.total_model_call_count = 0
    tb.tool_suggested = action
    tb.tool_executed = "true"
    tb.tool_result_present = "true"
    tb.executed_tool_name = action
    tb.local_tool_executed = action
    if manifest_meta:
        tb.capability_manifest_used = "Yes"
        tb.capabilities_count = int(manifest_meta.get("capabilities_count") or 0)
        tb.unavailable_capabilities_count = int(manifest_meta.get("unavailable_count") or 0)


def try_handle_interpreter_packet(
    message: str,
    interpreter_packet: dict,
    selected_model: str,
    mem_packet: dict,
    mem_context: str,
    tb,
    *,
    force_sync: bool = False,
) -> dict | None:
    """
    M4-A8.2-A — Run creative/local workflows from a single interpreter packet (no classifier).
    """
    from services.brain.command_interpreter import (
        CREATIVE_ACTIONS,
        interpreter_packet_to_ops_intent,
    )
    from services.brain.command_execution_kernel import KERNEL_LOCAL_ACTIONS
    from services.cockpit.action_service import execute_cockpit_action_for_chat
    from services.tools.live_ops_executor import try_execute_live_ops
    from services.brain.live_state_snapshot import build_neena_live_state_snapshot
    from services.tools.catalog import cockpit_ids, live_ops_ids

    action = (interpreter_packet.get("action") or "unknown").strip().lower()
    confidence = float(interpreter_packet.get("confidence") or 0.0)
    slots = dict(interpreter_packet.get("slots") or {})

    if action in cockpit_ids():
        local = execute_cockpit_action_for_chat(action, slots)
        if not local:
            return None
        _apply_local_ops_trace(tb, action)
        tb.step("response", f"Interpreter routed to local action {action}")
        local["_tb"] = tb
        return local

    live_ops_actions = live_ops_ids() | (KERNEL_LOCAL_ACTIONS - cockpit_ids())
    if action in live_ops_actions:
        snap = build_neena_live_state_snapshot()
        live = try_execute_live_ops(action, slots, snapshot=snap, owner_message=message)
        if live:
            cap_meta = live.pop("_capability_manifest_meta", None)
            _apply_local_ops_trace(tb, action, manifest_meta=cap_meta)
            tb.step("response", f"M4-A8.4 live ops executed: {action}")
            live.setdefault(
                "live_snapshot",
                {
                    "recommended_next_action": snap.get("recommended_next_action"),
                    "pending_scripts_count": snap.get("pending_scripts_count"),
                },
            )
            live["_tb"] = tb
            return live

    if action not in CREATIVE_ACTIONS:
        return None

    if not force_sync:
        from services.brain.creative_jobs import enqueue_creative_command_job
        from services.brain.load_shedding import build_load_defer_payload, is_load_high

        snap = build_neena_live_state_snapshot()
        if is_load_high(snap, 85.0):
            tb.source = "local_router"
            tb.route = "load_shed"
            out = build_load_defer_payload(snap)
            out["_tb"] = tb
            return out
        job = enqueue_creative_command_job(message, interpreter_packet, selected_model)
        tb.source = "creative_job"
        tb.route = "background"
        tb.step("response", f"Creative background job {job.get('job_id')}")
        return {
            "reply": job.get("message", "Creative job queue ho gayi."),
            "action_type": "CREATIVE_BACKGROUND",
            "job_id": job.get("job_id"),
            "mode": "background",
            "gemini_calls": 0,
            "ui_action": {
                "type": "poll_cockpit_job",
                "job_id": job.get("job_id"),
                "action_key": "creative_job",
            },
            "_tb": tb,
        }

    if confidence < LOW_CONFIDENCE_THRESHOLD:
        summary = interpreter_packet.get("owner_facing_summary") or ""
        reply = summary or "Clarify needed: RJ intro, ad script, or show plan?"
        tb.source = "local_router"
        tb.route = "clarification"
        tb.step("response", "Interpreter low confidence — clarification")
        return {"reply": reply, "action_type": "clarification", "_tb": tb}

    intent, extracted = interpreter_packet_to_ops_intent(interpreter_packet)
    packet = {
        "intent": intent,
        "confidence": confidence,
        "extracted_fields": extracted,
    }
    tb.intent_model_call_count = 1

    workflow_handlers = {
        "rj_intro": lambda: _workflow_rj_intro(message, packet, mem_packet, mem_context, selected_model, tb),
        "ad_script": lambda: _workflow_ad_script(message, packet, mem_packet, mem_context, selected_model, tb),
        "daily_show_plan": lambda: _workflow_daily_show_plan(
            message, packet, mem_packet, mem_context, selected_model, tb
        ),
        "create_broadcast_capsule": lambda: _workflow_create_broadcast_capsule(
            message, packet, mem_packet, mem_context, selected_model, tb
        ),
    }
    handler = workflow_handlers.get(intent)
    if not handler:
        return None

    result = handler()
    if result is None:
        return None

    # Living Station Clock plan is NOT a capsule — only real scripts queue.
    if intent in {"rj_intro", "ad_script", "create_broadcast_capsule"} and result.get("reply"):
        try:
            from services.broadcast.capsule_service import (
                append_capsule_footer,
                queue_script_and_create_capsule,
            )

            script_text = result["reply"].strip()
            if script_text:
                queued = queue_script_and_create_capsule(
                    script_text,
                    intent=intent,
                    source="interpreter_workflow",
                    metadata={"intent_confidence": confidence},
                )
                result["reply"] = append_capsule_footer(
                    script_text,
                    queued["approval_id"],
                    queued["capsule_id"],
                )
                result["approval_id"] = queued["approval_id"]
                result["capsule_id"] = queued["capsule_id"]
                result["approval_status"] = "pending_review"
                result["audio_truth_level"] = "none"
                result["azuracast_status"] = "blocked"
                tb.step(
                    "db_write",
                    f"Queued interpreter {intent} to approval {queued['approval_id']} capsule {queued['capsule_id']}",
                )
        except Exception as exc:
            logger.error("Failed to queue interpreter broadcast script: %s", exc)

    result["_tb"] = tb
    return result


def _workflow_create_broadcast_capsule(
    message: str, packet: dict, mem_packet: dict, mem_context: str, selected_model: str, tb
) -> dict | None:
    fields = packet.get("extracted_fields") or {}
    memory_block = _memory_snippet(mem_packet, mem_context)
    safe_note = ""
    if float(packet.get("confidence") or 0) < MEDIUM_CONFIDENCE_THRESHOLD:
        safe_note = "Keep script conservative; owner intent confidence is medium."

    length_rule, max_tok = _script_length_policy(message)
    system = f"""You are Neena Gupta, AI Station Manager of Orai Radio.
Write a fresh broadcast update or radio show script based on the owner request.
{safe_note}

Rules:
- Bundeli/Hinglish comedy or friendly tone when memory or request says so
- Energetic, clean, non-vulgar, directly usable on air
- {length_rule}
- Do NOT use fixed templates; generate new content each time
- Do NOT mention Stage M1 or blocked memory
- Output ONLY the script text (no meta commentary)

{memory_block}

Owner extracted hints: {json.dumps(fields, ensure_ascii=False)}"""

    reply, provider, status, model_id = _generate_with_gemini(
        system, message, selected_model, max_tokens=max_tok
    )
    if status != "available" or not reply:
        _mark_generation_unavailable(tb, status, model_id)
        reply = "Orai Radio ke sabhi listeners ko mera pranam! Aaj ke show me hum baat karenge ek dilchasp topic par..."
        tb.llm_used = False
        tb.llm_provider = "local"
        tb.llm_status = "local_template_fallback"
        tb.actual_model = None
        tb.response_composer_model_used = "local_template"
        tb.response_model_call_count = 0
        tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0)
        tb.source = "local_fallback"
        tb.route = "create_broadcast_capsule"
        tb.final_reply_source = "operations_workflow_local_fallback"
        tb.step("response", f"Broadcast capsule local template fallback (gen status={status})")
    else:
        tb.llm_used = True
        tb.llm_provider = provider
        tb.llm_status = status
        tb.actual_model = model_id
        tb.response_composer_model_used = model_id or "gemini-3.1-flash-lite"
        tb.response_model_call_count = 1
        tb.total_model_call_count = int(getattr(tb, "intent_model_call_count", 0) or 0) + 1
        tb.source = f"{provider}_api"
        tb.route = "create_broadcast_capsule"
        tb.final_reply_source = "operations_workflow_gemini"
        tb.step("response", "Broadcast capsule workflow generated via Gemini")

    return {"reply": reply, "action_type": "CREATE_BROADCAST_CAPSULE"}


__all__ = ["try_handle_operations", "try_handle_interpreter_packet", "build_station_status_reply"]

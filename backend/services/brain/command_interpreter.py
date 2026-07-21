"""M4-A8.2-A / M4-A8.5.2 — Single model call command interpreter (JSON action packet)."""
from __future__ import annotations

import json
import logging

import requests

import services.llm.provider_router as pr
from services.safety.security_config import get_ssl_verify
from services.brain.command_execution_kernel import normalize_action_key
from services.llm.model_roles import MODEL_ROLE_CONFIG, resolve_role_to_api_id

logger = logging.getLogger(__name__)

INTERPRETER_TIMEOUT_SECONDS = 18.0
# Primary Gemma budget for intent classification: if Gemma is slow, fall back to
# fast flash-lite so routing never stalls ~20s (only when a fallback exists).
GEMMA_SOFT_TIMEOUT_SECONDS = 8.0
LOW_CONFIDENCE_THRESHOLD = 0.45

# M4-A2 Safety Patch: broadcast commands MUST route to send_azuracast, never generate_audio.
# Any command matching these patterns is reclassified to send_azuracast post-LLM.
from services.safety.kernel import BROADCAST_PROTECTED_PATTERNS, EXPLICIT_AUDIO_INTENTS

# Derived from neena_tool_catalog — do not hand-edit this frozenset.
def _catalog_valid_actions() -> frozenset:
    from services.tools.catalog import valid_actions_with_unknown

    return valid_actions_with_unknown()


def __getattr__(name: str):
    if name == "VALID_ACTIONS":
        return _catalog_valid_actions()
    if name == "CREATIVE_ACTIONS":
        from services.tools.catalog import creative_ids

        return creative_ids()
    if name == "LOCAL_ACTIONS":
        from services.tools.catalog import cockpit_ids

        # Legacy LOCAL_ACTIONS included verify_stream + broadcast_readiness;
        # cockpit route owns station_status/diagnostics. Keep verify via live_ops.
        return cockpit_ids() | frozenset({"verify_stream", "broadcast_readiness"})
    if name == "INTERPRETER_SYSTEM":
        return get_interpreter_system()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


INTERPRETER_SYSTEM_TEMPLATE = """You are Neena Gupta's command interpreter for Orai Radio Command Center.
Understand the owner's natural language (Hindi, Hinglish, English) and return ONLY valid JSON.

Required JSON:
{{
  "action": "{action_enum}",
  "confidence": 0.0-1.0,
  "slots": {{ }},
  "needs_confirmation": false,
  "owner_facing_summary": "short Hinglish summary of what owner wants"
}}

slots examples:
- station_status: requested_scope (full|short|health_only)
- explain_button: button_name or button_id (approve|audio|azuracast|verify|status)
- create_rj_intro: show_time, tone, local_touch_requested, length_preference
- create_ad_script: business_name, duration_seconds, tone, cta_preference
- create_station_plan: living Station Clock for next 3–4h (or day chunks).
  slots horizon (shift_3h|shift_4h|day), theme?, hours?. NOT a Lab capsule.
  Alias: create_daily_show_plan → create_station_plan.
- get_station_plan / advance_station_plan / draft_plan_block: read/advance/draft next clock block
- create_broadcast_capsule: topic, language, tone, creator
- approve_capsule: capsule_id (optional int), approved_by (optional)
- reject_capsule: capsule_id (optional int), reject_reason (required string if given), rejected_by (optional)
- prepare_capsule_audio: capsule_id (optional int)
- capsule_status: capsule_id (optional int)
- verify_stream: watch_seconds (optional int)
- diagnose_listener_path: app me stream/play nahi, listener path check, public app offline/play fail,
  'app stream check', 'app me awaaz nahi' — diagnose ONLY (no URL write)
- fix_app_listener_path: owner clearly wants remote app_config stream/api URL theek/set —
  'app stream theek karo', 'app URL fix karo'. Set needs_confirmation true unless already confirming.
- check_interaction_recorder: slots limit (optional int 3-30), channel (optional chat|whatsapp)
- customer_whatsapp_recall: slots phone_digits (optional last-10), date_ist (optional YYYY-MM-DD),
  window (optional today|yesterday), limit (optional int 10-80)
- approve_latest_script: explicit_approval (bool) when owner clearly says approve karo

Guidelines:
- capabilities: owner asks tool/capability LIST — 'kya kar sakti ho', 'kya features hain',
  'what can you manage'. Role/job/identity ('tumhara kaam kya hai', 'tum kya karti ho')
  capabilities NAHI — wo self-knowledge hai, action "unknown".
- model_status: model/brain/cooldown/rate limit questions
- memory_status: permanent memory / pgvector / redis memory stack questions
- customer_whatsapp_recall: owner asks about customer/listener WhatsApp messages,
  leads, inquiries, "kisi ne message kiya", "aaj customer se baat hui", "kis kis se baat",
  or a specific phone's chat. ALWAYS this action — never unknown/conversation and never
  invent "koi message nahi" without the tool. Read-only checked recorder/Redis facts.
  NOT check_interaction_recorder (CC self-check) and NOT day_memory_recall / memory_status.
  NEVER invent a send_whatsapp_message tool — outbound to customers is not available.
- check_interaction_recorder: owner wants Neena to READ recent interaction recorder /
  command-center history for self-check (galti, confirm loop, last turns). Read-only.
  NOT memory_status and NOT diagnostics/station_status.
- admin_lock: owner wants Command Center / admin UI locked (UI lock action).
- auth_session_explain: owner asks how long unlock/session/cookie lasts.
- arm_deferred_status: owner wants a later WhatsApp status push (e.g. N min baad status
  bhej dena). Catalog arms one deferred job — never invent a timer in chat.
- timeout_diagnosis: why commands are slow or timing out
- what_should_i_do_now: ab kya karna hai, next step, kya karun
- station_status: system/station health, status batao, kaisa chal raha
- diagnostics: owner wants diagnostics/health scan
- pipeline_status: pending scripts, approval queue status, broadcast pipeline
- explain_button: owner asks what a UI button does (Approve, Audio, AzuraCast, Verify Stream)
- open_latest_script: owner wants latest/pending script opened for review
- approve_latest_script: owner wants latest pending script approved
- generate_audio: ONLY when owner explicitly asks to generate/prepare audio/voice for a capsule.
  Example: 'audio banao', 'voice preview banao', 'prepare audio'. NEVER use for broadcast/air/upload commands.
- send_azuracast: ONLY for broadcast/upload/air/push-to-station commands.
  Example: 'broadcast now', 'broadcast karo', 'air karo', 'chala do', 'live karo', 'station pe bhejo'.
  CRITICAL: 'broadcast now', 'chala do', 'air karo', 'live karo' must ALWAYS be send_azuracast, NEVER generate_audio.
- ensure_playback: confirm playback is running on air
- create_rj_intro / create_ad_script / create_broadcast_capsule: creative scripts (capsules)
- create_station_plan / draft_plan_block: Station Clock living plan (not show_plan capsule)
- create_broadcast_capsule: owner wants a naya update / broadcast script, e.g. "morning update script banao"
- list_pending_capsules: pending scripts list dikhao
- open_latest_capsule: latest capsule kholo
- approve_capsule: approve specific capsule or latest pending capsule
- reject_capsule: reject capsule with slots reason
- prepare_capsule_audio: approved script/capsule audio ready/generate karo
- capsule_status: capsule ka status check karo
- set_response_style: owner apni reply-length preference bata rahe hain.
  Examples: 'short rakho', 'chhota jawab do', 'itna detail mat do', 'brief mein batao',
  'ab se short', 'poora data mat dikhao' -> slots {{"verbosity": "short"}}.
  Ya 'full detail do', 'poora batao', 'detail mein' -> slots {{"verbosity": "normal"}}.
- send_owner_whatsapp_status: owner chahte hain ki Neena unhe WhatsApp par status/update bheje.
  Examples: 'mujhe WhatsApp pe status bhejo', 'WhatsApp par update karo', 'apne aap message karo',
  'WhatsApp pe bata dena'. slots {{"topic": "status" | free text}}.
- time_status: owner abhi ka time, date, ya din pooch rahe hain.
  Examples: 'time kya hua', 'time kitna hua hai', 'abhi kitne baje hain', 'date batao',
  'aaj kaunsi tareekh hai', 'time or date batayo', 'aaj kaunsa din hai'.
  Ye kabhi station_status ya diagnostics NAHI hai — ye sirf clock/calendar sawaal hai.
- manage_memory: owner apni SAVED permanent memories dekhna, badalna (correct/replace)
  ya hataana (delete) chahte hain. Ye memory-stack HEALTH (memory_status) NAHI hai.
  slots {{"operation": "list" | "update" | "delete",
         "target": <stable memory id from list, e.g. "27", OR short description>,
         "new_content": <update ke liye naya text>}}.
  Examples:
    'yaadein dikhao' / 'kya kya save hai' / 'meri saved memories dikhao' / 'sari yade dikhayo'
      -> operation list.
    'memory id 27 delete karo' / 'id 27 hata do' / 'ye rule hata do'
      -> operation delete, target = that id or description (NOT a new save).
    'memory id 27 badlo: RJ tone ab Hinglish rakho' / 'id 27 replace karo: <naya text>'
      -> operation update, target = id, new_content = naya text.
  CRITICAL: list / delete / replace / correction of an EXISTING saved memory is ALWAYS
  manage_memory — NEVER propose_permanent_memory.
- propose_permanent_memory: owner chahta hai koi NEW preference/rule/fact PERMANENT save ho
  (yaad rakh / always remember this / prefer X / aise karo / aage se / save this fact).
  slots {{"content": <exact one line to save>,
         "memory_type": optional owner_style_preference | operational_preference |
         station_policy | content_tone_rule | station_identity | approved_workflow_rule |
         neena_self_identity | neena_personality_profile | neena_life_episode |
         neena_mind_architecture}}.
  Owner directive ALREADY confirm hai — same turn AUTO-SAVE (no second haan). Soft ACK
  system dega. Magic phrase zaroori nahi.
  NEVER use propose_permanent_memory for: yaadein dikhao, delete, replace, correction,
  "no. N bali", or when owner is pointing at an existing list item.
  NEVER put bare confirm words (haan/hann/han/yes) into slots.content.
- unknown: casual chat, feedback, frustration, ya unclear request — natural baat-cheet.
  NEVER use unknown to imply station work already started (audio generate, queue, AzuraCast
  push, customer WhatsApp send). Work asks MUST pick a catalog action; if no matching hand,
  still pick the closest catalog action or unknown — execution/Cannot is kernel+truth_gate,
  not invented in owner_facing_summary.

CRITICAL CONVERSATION & FEEDBACK RULE (highest priority — ise sabse pehle check karo):
- Jab owner FEEDBACK de, naaraaz ho, ya complaint kare ki aap unki baat/intent nahi samajh
  rahi, galat kaam kiya, reply robotic/purana hai — to action ALWAYS "unknown" (natural reply).
  Ye kabhi bhi diagnostics, station_status, ya memory_status NAHI hai.
  Examples jo "unknown" hone chahiye:
    'tum meri baat nahi samajh rahi', 'galat intent samjha', 'ye bakwas hai',
    'phir se galti ki', 'intent samajhne mein gap hai', 'tum theek se nahi samajh rahi',
    'ye purana default message hai', 'aise reply mat do'.
- diagnostics / station_status SIRF tab jab owner clearly system/station health ya scan
  maange: 'diagnostics chalao', 'station status batao', 'sab theek hai kya', 'health check'.
  Owner ki frustration ya complaint ko kabhi diagnostics/status samajh kar mat route karo.
- meta-question — owner puchhe ki aapne pichhla reply kaise/kaunse route/model se diya,
  'LLM se aaya ya local', 'kaun sa route use hua' — action "model_status".
- memory_status SIRF memory system/stack HEALTH ke liye (Postgres/Redis/pgvector healthy?).
  'tumhe kya kya yaad hai / what do you remember / meri kaun si baat yaad hai' memory_status
  NAHI — recall hai, action "unknown".
- SELF IDENTITY / LIFE STORY / ARCHITECTURE: 'tum kaun ho', 'apna parichay', 'zindagi / kahani',
  'personality', 'dimaag kaise', 'architecture', 'kis file', 'Safety Kernel', 'one-brain' —
  action "unknown" (natural) OR left for brain local self-narrative retrieval
  (neena_self_identity / personality / life_episode / mind_architecture). Ye memory_status NAHI.
- DAY / CALENDAR MEMORY (owner timeline only): 'kal kya hua', 'parso', 'aaj kya discuss',
  'YYYY-MM-DD', 'is hafte' — action "day_memory_recall" (owner CC/WA diary). 
  Agar sawaal CUSTOMER/listener/lead/WhatsApp inquiry hai ("kis se baat", "kisi ne message")
  to day_memory_recall NAHI — customer_whatsapp_recall. Ye memory_status NAHI.
- SELF / BODY AWARENESS (health RIGHT NOW): 'kaisi ho', 'tumhara shareer', 'redis postgres docker
  tumhare andar', 'kuch toot gaya kya', 'healthy ho' — action ALWAYS "unknown" so conversation
  layer LIVE body feel use kare. Static body dump expect mat karo — realtime check.
  Identity notebook alag hai; hurt/healthy is turn ka probe alag hai.
- set_response_style ke natural phrasings bhi pakdo: 'chat mein aam bhasha mein reply do',
  'ye background technical cheezein front pe mat dikhao', 'simple language mein baat karo',
  'har baar poora data mat dikhao' -> action set_response_style, slots {{"verbosity": "short"}}.

CONTINUITY RULE:
- Recent conversation turns aapko diye gaye hain. Follow-up ya reference wale short messages
  ('matlab?', 'wahi karo', 'phir se batao', 'jo plan/baat hamne discuss ki thi', 'usko save karo')
  ko un pichhle turns ke context me samjho — akela literal mat lo. Agar owner pichhli baat ki
  taraf ishara kar raha hai aur clear action nahi banta, to action "unknown" (natural reply)
  rakho, koi galat command (jaise capsule kholna) mat trigger karo.

CRITICAL SAFETY RULE:
- 'broadcast now', 'broadcast karo', 'air karo', 'chala do', 'live karo', 'on air karo',
  'station pe bhejo', 'play it', 'send to azuracast' MUST ALWAYS map to send_azuracast.
- These commands must NEVER map to generate_audio or any audio generation action.
- Only map to generate_audio when owner clearly and explicitly says to generate/prepare audio or voice.

Do not invent business names. Output raw JSON only."""


def get_interpreter_system() -> str:
    from services.tools.catalog import build_interpreter_action_enum

    return INTERPRETER_SYSTEM_TEMPLATE.format(action_enum=build_interpreter_action_enum())


FALLBACK_PACKET = {
    "action": "unknown",
    "confidence": 0.0,
    "slots": {},
    "needs_confirmation": False,
    "owner_facing_summary": "Request samajh nahi aayi.",
}


def build_interpreter_unavailable_packet(reason: str = "interpreter_unavailable") -> dict:
    """Structured failure when interpreter cannot run — never regex-fallback.

    action stays ``unknown`` (not model_status) so cooldown/rate-limit does not
    hijack owner asks like pipeline/memory into a model dump.
    """
    return {
        "action": "unknown",
        "confidence": 0.0,
        "slots": {"reason": reason},
        "needs_confirmation": False,
        "owner_facing_summary": "",
    }


def build_interpreter_timeout_reply(snapshot: dict | None = None) -> str:
    # Keep a short human reply — never imply the backend went silent.
    del snapshot
    return (
        "Sir, abhi model thoda slow chal raha hai, isliye intent clear nahi pakad paayi. "
        "Status, time, yaad, ya koi short command dobara bol dijiye — main turant try karti hoon."
    )


def _extract_response_text(res_json: dict) -> str:
    """Skip thinking-model parts; collect visible text only."""
    text = ""
    for part in res_json.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if part.get("thought"):
            continue
        text += part.get("text", "")
    return text.strip()


def _normalize_packet(raw: dict) -> dict:
    packet = dict(raw)
    action = normalize_action_key(packet.get("action") or "unknown")
    if action not in _catalog_valid_actions():
        action = "unknown"
    packet["action"] = action
    try:
        packet["confidence"] = float(packet.get("confidence") or 0.0)
    except (TypeError, ValueError):
        packet["confidence"] = 0.0
    packet["slots"] = packet.get("slots") or {}
    packet["needs_confirmation"] = bool(packet.get("needs_confirmation"))
    packet["owner_facing_summary"] = (packet.get("owner_facing_summary") or "").strip()
    return packet


def _safety_reclassify(packet: dict, user_message: str) -> dict:
    """M4-A2 Safety Patch: post-LLM reclassifier.
    
    Overrides the LLM result if a broadcast command was misrouted to generate_audio.
    Also blocks generate_audio if message is ambiguous (not an explicit audio intent).
    This runs AFTER the LLM responds and is a hard gate — cannot be disabled.
    """
    msg_lower = (user_message or "").lower().strip()
    action = packet.get("action", "")

    # Rule 1: If any broadcast pattern matches, force send_azuracast regardless of LLM decision
    for pattern in BROADCAST_PROTECTED_PATTERNS:
        if pattern in msg_lower:
            if action != "send_azuracast":
                logger.warning(
                    "[SAFETY_RECLASSIFY] Broadcast pattern '%s' in '%s' — overriding action '%s' -> send_azuracast",
                    pattern, msg_lower[:80], action
                )
                packet = dict(packet)
                packet["action"] = "send_azuracast"
                packet["_safety_reclassified"] = True
                packet["_original_action"] = action
                packet["_reclassify_reason"] = f"broadcast_pattern_match:{pattern}"
            return packet

    # Rule 2: If LLM chose generate_audio, verify the message contains an explicit audio intent.
    # If not, block it by reclassifying to unknown (safe fallback).
    if action in ("generate_audio", "prepare_capsule_audio"):
        has_explicit_audio_intent = any(intent in msg_lower for intent in EXPLICIT_AUDIO_INTENTS)
        if not has_explicit_audio_intent:
            logger.warning(
                "[SAFETY_RECLASSIFY] generate_audio routed without explicit audio intent in '%s' — overriding to unknown",
                msg_lower[:80]
            )
            packet = dict(packet)
            packet["_original_action"] = action
            packet["action"] = "unknown"
            packet["_safety_reclassified"] = True
            packet["_reclassify_reason"] = "no_explicit_audio_intent"

    return packet


def _routing_truth_reclassify(packet: dict, user_message: str) -> dict:
    """Override misrouted LLM actions for auth/status gates."""
    from services.brain.deterministic_routes import resolve_deterministic_action

    det = resolve_deterministic_action(user_message)
    if not det:
        return packet
    target = det["action"]
    current = packet.get("action", "")
    if current == target:
        return packet
    override_from = {
        "timeout_diagnosis",
        "diagnostics",
        "station_status",
        "unknown",
        "capabilities",
    }
    if current in override_from or (target == "vm_status" and current == "capsule_status"):
        logger.info(
            "[ROUTING_TRUTH] Overriding action '%s' -> '%s' for owner message",
            current,
            target,
        )
        packet = dict(packet)
        packet["action"] = target
        packet["_routing_truth_reclassified"] = True
    return packet


def _interpreter_model_chain(available: set[str]) -> list[str]:
    """Primary + fallback API ids for interpreter role (deduped)."""
    seen: set[str] = set()
    chain: list[str] = []
    primary = resolve_role_to_api_id("COMMAND_INTERPRETER_MODEL", available)
    if primary:
        chain.append(primary)
        seen.add(primary)
    cfg = MODEL_ROLE_CONFIG.get("COMMAND_INTERPRETER_MODEL") or {}
    fb_option = cfg.get("fallback_option")
    if fb_option:
        for cid in pr.get_model_candidates(fb_option):
            if cid in available and cid not in seen and not pr.is_disallowed_normal_flow_model(cid):
                chain.append(cid)
                seen.add(cid)
    for cid in cfg.get("candidate_api_ids") or []:
        if cid in available and cid not in seen and not pr.is_disallowed_normal_flow_model(cid):
            chain.append(cid)
            seen.add(cid)
    return chain


def deterministic_interpreter_fallback(message: str) -> dict | None:
    """M4-A8.5.2 — Keyword routing removed; always None (use model_status packet instead)."""
    del message
    return None


def _call_interpreter_model(
    resolved_id: str,
    api_key: str,
    user_message: str,
    system_inst: str,
    history_contents: list | None = None,
    timeout_seconds: float = INTERPRETER_TIMEOUT_SECONDS,
    *,
    wait_out_cooldown: bool = False,
) -> tuple[dict | None, str, str]:
    """Returns (packet_or_none, provider, status)."""
    if pr.is_disallowed_normal_flow_model(resolved_id):
        return None, "none", "model_unavailable"

    provider = "gemma" if "gemma" in resolved_id else "gemini"
    gen_cfg: dict = {"temperature": 0.1, "maxOutputTokens": 500}
    if "gemini" in resolved_id:
        gen_cfg["responseMimeType"] = "application/json"
    contents = list(history_contents or [])
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_inst}]},
        "generationConfig": gen_cfg,
    }

    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=timeout_seconds,
            priority="owner",
            purpose="interpreter",
            wait_out_cooldown=wait_out_cooldown,
        )
        use_id = meta.get("model_id") or resolved_id
        provider = "gemma" if "gemma" in use_id else "gemini"
        if status == "cooldown":
            pkt = build_interpreter_unavailable_packet("cooldown")
            pkt["owner_facing_summary"] = pr.build_owner_cooldown_reply(meta.get("cooldown_wait"))
            return pkt, provider, "cooldown"
        if status == "quota_deferred":
            pkt = build_interpreter_unavailable_packet("quota_deferred")
            from services.llm.quota_gatekeeper import build_quota_defer_reply

            pkt["owner_facing_summary"] = build_quota_defer_reply(role="owner")
            return pkt, provider, "quota_deferred"
        if status != "available" or not data:
            return None, provider, status if status in ("rate_limited", "timeout") else "provider_error"
        text = _extract_response_text(data)
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
        if not text:
            return None, provider, "provider_error"
        packet = _normalize_packet(json.loads(text))
        return packet, provider, "available"
    except Exception as exc:
        logger.error("Command interpreter model %s failed: %s", resolved_id, exc)
        return None, provider, "provider_error"


def interpret_owner_command(
    user_message: str,
    memory_context: str = "",
) -> tuple[dict, str, str, str | None]:
    """
    One interpreter model call (model chain only — no keyword fallback).
    Returns (packet, provider, status, resolved_model_id).

    M4-A2 Safety: _safety_reclassify() is applied after every successful LLM response
    to prevent broadcast commands from routing to generate_audio or TTS.
    """
    msg_lower = (user_message or "").lower().strip()

    from services.brain.deterministic_routes import resolve_deterministic_action

    det = resolve_deterministic_action(user_message)
    if det:
        return det, "local", "available", None

    # Capsule / schedule / status: interpreter LLM + catalog only (no Hinglish string gates).
    api_key = pr.get_gemini_api_key()
    if not api_key:
        pkt = build_interpreter_unavailable_packet("no_api_key")
        return pkt, "none", "unavailable", None

    available = set(pr.get_available_api_models(api_key, allow_network_refresh=False))
    model_chain = _interpreter_model_chain(available)
    if not model_chain:
        pkt = build_interpreter_unavailable_packet("model_unavailable")
        return pkt, "none", "model_unavailable", None

    system_inst = get_interpreter_system()
    if memory_context:
        system_inst += f"\n\nMemory context (classification only):\n{memory_context[:2000]}"

    # Continuity: give the interpreter the recent conversation so follow-up/reference
    # messages ("matlab?", "jo plan discuss kiya tha") are understood in context.
    history_contents: list = []
    try:
        from services.memory.continuity import load_owner_continuity

        history_contents = list(
            (load_owner_continuity(chat_limit=4).get("chat_turns") or [])
        )
    except Exception:
        try:
            import services.memory.adapter as memory_adapter

            history_contents = memory_adapter.load_chat_history_contents(limit=4)
        except Exception:
            history_contents = []

    last_provider = "none"
    last_status = "model_unavailable"
    last_model: str | None = None

    for idx, resolved_id in enumerate(model_chain):
        # Primary Gemma gets a short budget so slow Gemma falls back to fast flash-lite.
        soft = "gemma" in resolved_id and idx == 0 and len(model_chain) > 1
        # If Gemma just timed out this turn, skip it and go straight to the fast fallback.
        if soft and pr.is_model_penalized(resolved_id):
            last_status = "timeout"
            continue
        per_call_timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else INTERPRETER_TIMEOUT_SECONDS
        is_last = idx == len(model_chain) - 1
        packet, provider, status = _call_interpreter_model(
            resolved_id, api_key, user_message, system_inst, history_contents, per_call_timeout,
            wait_out_cooldown=is_last,
        )
        last_provider = provider
        last_status = status
        last_model = resolved_id
        if status == "available" and packet:
            # M4-A2 Safety: always reclassify after LLM responds
            packet = _safety_reclassify(packet, user_message)
            packet = _routing_truth_reclassify(packet, user_message)
            return packet, provider, status, resolved_id
        if status == "cooldown" and packet:
            return packet, provider, status, resolved_id

    if last_status == "timeout":
        pkt = build_interpreter_unavailable_packet("interpreter_timeout")
        pkt["owner_facing_summary"] = build_interpreter_timeout_reply()
        return pkt, last_provider, "timeout", last_model

    pkt = build_interpreter_unavailable_packet(f"interpreter_{last_status}")
    if last_status in ("rate_limited", "provider_error", "model_unavailable"):
        pkt["owner_facing_summary"] = (
            "Model abhi available nahi hai. Cockpit Status/Diagnostics buttons use kariye, "
            "ya thodi der baad try kariye."
        )
    return pkt, last_provider, last_status, last_model


def interpreter_packet_to_ops_intent(packet: dict) -> tuple[str, dict]:
    """Map interpreter packet to legacy operations workflow intent + extracted_fields."""
    action = packet.get("action") or "unknown"
    slots = dict(packet.get("slots") or {})
    mapping = {
        "create_rj_intro": "rj_intro",
        "create_ad_script": "ad_script",
        "create_broadcast_capsule": "create_broadcast_capsule",
        "station_status": "station_status",
        "diagnostics": "diagnostics",
    }
    intent = mapping.get(action, "general_chat")
    if action == "station_status" and "requested_scope" not in slots:
        slots["requested_scope"] = "full"
    return intent, slots


__all__ = [
    "BROADCAST_PROTECTED_PATTERNS",
    "CREATIVE_ACTIONS",
    "EXPLICIT_AUDIO_INTENTS",
    "INTERPRETER_SYSTEM",
    "INTERPRETER_TIMEOUT_SECONDS",
    "LOCAL_ACTIONS",
    "LOW_CONFIDENCE_THRESHOLD",
    "VALID_ACTIONS",
    "build_interpreter_timeout_reply",
    "build_interpreter_unavailable_packet",
    "deterministic_interpreter_fallback",
    "get_interpreter_system",
    "interpret_owner_command",
    "interpreter_packet_to_ops_intent",
]

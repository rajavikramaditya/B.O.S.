"""M5 — Natural conversational reply layer for Neena.

This is the layer that was previously dead code inside process_owner_message.
It generates a grounded, natural Hinglish reply using an LLM (Gemma-first) when
the message is conversational / unclear / not a structured command — instead of
returning canned template text.

Design guarantees (owner requirements):
- Generic: used for ALL conversational turns, not per-command.
- No false claims ("gemini jhutt na kre"): the model is told to never claim an
  action ran, and to only report a live status if it was checked this turn and
  provided in context; otherwise it must say it was not checked.
- Real memory use (not "whole chat every time"): only the last few turns are
  injected as short-term context, plus relevant retrieved permanent memories.
"""
from __future__ import annotations

import json
import logging

import requests

import services.llm.provider_router as pr
import services.brain.feature_flags as feature_flags
import services.memory.adapter as memory_adapter
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

CONVERSATION_TIMEOUT_SECONDS = 30.0
# Owner rule: reply must ALWAYS come fast. Gemma is primary but can be slow (30-44s).
# Give the primary Gemma call a short budget; if it doesn't answer in time, fall back
# to flash-lite (fast) so the owner never waits ~40s. Only applied when a fallback
# model actually exists (if Gemma is the only option, it keeps the full timeout).
GEMMA_SOFT_TIMEOUT_SECONDS = 10.0
CONVERSATION_HISTORY_TURNS = 14


def _conversation_model_chain(api_key: str) -> list[str]:
    """Gemma-first chain with a Gemini flash-lite fallback (deduped, approved only)."""
    chain: list[str] = []
    primary = pr.resolve_model_for_role("CONVERSATION_MODEL")
    if primary and not pr.is_disallowed_normal_flow_model(primary):
        chain.append(primary)
    gemini_fb = pr.resolve_and_verify_model("gemini-3.1-flash-lite", api_key)
    if gemini_fb and gemini_fb not in chain and not pr.is_disallowed_normal_flow_model(gemini_fb):
        chain.append(gemini_fb)
    return chain


def _memory_block(mem_packet: dict | None, mem_context: str | None) -> str:
    """Build the RECENT SAVED MEMORY section for the conversation prompt.

    Permanent hits and mem_context are BOTH kept when present. Dropping
    mem_context whenever hits exist caused a live trust failure: owner asked
    about customer WhatsApp, brain injected recorder threads into mem_context,
    then this helper discarded them and the LLM invented "koi message nahi aaya".
    """
    parts: list[str] = []
    lines: list[str] = []
    for hit in (mem_packet or {}).get("hits") or []:
        if (hit or {}).get("source") == "short_term":
            continue
        content = (hit.get("content") or "").strip()
        if content:
            lines.append(f"- {content}")
    if lines:
        parts.append(
            "Saved permanent memories relevant to Sir's message:\n" + "\n".join(lines)
        )
    ctx = (mem_context or "").strip()
    if ctx:
        # Prefer full enriched blocks (customer threads / STM) over a tiny stub.
        budget = 4000 if "CUSTOMER WHATSAPP" in ctx else 2000
        parts.append(ctx[:budget])
    if not parts:
        return "No specific saved memory hit for this message."
    return "\n\n".join(parts)


def _snapshot_block(live_snapshot: dict | None) -> str:
    if not live_snapshot:
        return "No live status was checked this turn."
    try:
        from services.brain.live_state_snapshot import format_snapshot_for_interpreter

        return format_snapshot_for_interpreter(live_snapshot)
    except Exception:
        return "No live status was checked this turn."


def build_conversation_system_prompt(mem_packet: dict | None, mem_context: str | None, live_snapshot: dict | None) -> str:
    memory_block = _memory_block(mem_packet, mem_context)
    snapshot_block = _snapshot_block(live_snapshot)
    try:
        from services.brain.self_knowledge import format_body_awareness_for_llm
        body_block = format_body_awareness_for_llm()
    except Exception:
        body_block = "LIVE BODY FEEL: is turn body check fail hua — guess mat karo."
    try:
        from services.agent.system_knowledge_pack import system_knowledge_pack_text
        from services.memory.continuity import build_owner_prompt_context

        pack_block = system_knowledge_pack_text()
        prompt_ctx = build_owner_prompt_context("")
        work_block = prompt_ctx.get("working_block") or ""
        clock_block = prompt_ctx.get("clock_block") or ""
    except Exception:
        pack_block = ""
        work_block = ""
        clock_block = ""
        try:
            from services.agent.working_context import format_working_context_block

            work_block = format_working_context_block()
        except Exception:
            work_block = ""
    pack_section = f"\n{pack_block}\n" if pack_block else ""
    work_section = f"\n{work_block}\n" if work_block else ""
    clock_section = f"\n{clock_block}\n" if clock_block else ""
    return f"""You are Neena Gupta, the Station Manager of Orai Radio, talking to the station owner ("Sir").
Reply in natural, warm Hinglish (Hindi + English) with feminine grammar ("kar rahi hoon", "samajh gayi", "bataati hoon"). Sound like a real, helpful human station manager — NOT a robotic status machine.

{body_block}
{clock_section}{pack_section}{work_section}
HOW TO REPLY:
- Answer the owner's actual message directly and conversationally. Keep it short and human.
- If Sir asks about YOU / your body / health / redis-postgres-docker / "kaisi ho" in a self sense: use LIVE BODY FEEL above — like a person who knows their hands/eyes AND knows when something is hurt. Do NOT recite a memorized paragraph. Say what is healthy vs hurt RIGHT NOW.
- Do NOT dump a system status list (CPU/RAM/stream/memory bullet points) unless the owner explicitly asked for status/health. For casual talk, just talk naturally.
- Do NOT re-introduce yourself ("Main Neena Gupta bol rahi hoon") in every reply. Only if Sir asks who you are.
- Use the recent conversation turns provided to stay in context. If Sir asks "hamne kya discuss kiya" / "tumhe yaad hai", answer from the recent conversation turns given below. If it is not in the provided turns, honestly say you don't have that earlier context right now.
- Command Center aur WhatsApp ek hi owner conversation history share karte hain — channel alag hone se memory erase nahi hoti.
- Use OWNER WORKING CONTEXT for follow-ups ("result?", "usi id ko badlo", "haan") when present.
- Use saved permanent memories naturally when relevant to what Sir is asking (owner facts) — not as a substitute for live body feel.

TRUTH RULES (very important — never lie):
- Ada-style control: no tool/job FACTS this turn = no station progress claim. Missing hand = say you cannot / need a catalog tool — never invent generate/queue/trigger/"kar dungi".
- NEVER claim you performed, ran, started, or completed any action (diagnostics, broadcast, restart, upload, audio, capsule, WhatsApp send) in this reply. You only talk; a separate safe system executes actions.
- NEVER claim sleep mode, standby-only, paused background jobs, stopped downloads, or halted processes — you have no such capability unless a tool result this turn proves it.
- NEVER claim you saved, remembered, or stored anything to permanent memory unless a tool/result in THIS turn already completed a permanent write. You cannot write memory from conversation alone. If a permanent write already succeeded this turn, a short human ACK is fine ("samajh gayi / aage se dhyan dungi"). Do NOT ask Sir for a second haan on preferences he already stated. Delete/overwrite still needs confirm — do not fake those.
- Only state a live service status if it appears in LIVE BODY FEEL or LIVE STATUS below. If not checked, say so — never invent healthy/hurt. If LIVE BODY FEEL shows CPU hurt/high, do not call the body healthy overall.
- Use LIVE CLOCK above for any time; never reuse an older time from chat history.
- Never invent numbers, news, weather, traffic, or facts. If you don't know, say so plainly.
- If a factual tool packet / CUSTOMER WHATSAPP data appears in context: summarize ONLY what is checked. If status is empty / NONE, say you checked and found none. Never invent customer chats that were not checked this turn.
- If the owner points out a mistake or gives feedback about you, acknowledge it honestly and briefly — do not deflect with a status dump.

RECENT SAVED MEMORY:
{memory_block}

LIVE STATUS (station/ops; only if Sir asked about station status):
{snapshot_block}
"""


def _call_conversation_model(
    resolved_id: str,
    api_key: str,
    system_prompt: str,
    contents: list[dict],
    timeout_seconds: float = CONVERSATION_TIMEOUT_SECONDS,
    *,
    wait_out_cooldown: bool = False,
) -> tuple[str, str, str]:
    """Returns (reply_text, provider, status)."""
    provider = "gemma" if "gemma" in resolved_id else "gemini"
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 800},
    }
    try:
        data, status, meta = pr.call_generate_content_json(
            resolved_id,
            api_key,
            payload,
            timeout=timeout_seconds,
            priority="owner",
            purpose="conversation",
            wait_out_cooldown=wait_out_cooldown,
        )
        use_id = meta.get("model_id") or resolved_id
        provider = "gemma" if "gemma" in use_id else "gemini"
        if status != "available" or not data:
            return "", provider, status if status else "provider_error"
        text = ""
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if part.get("thought"):
                continue
            text += part.get("text", "")
        text = text.strip()
        if not text:
            return "", provider, "provider_error"
        return text, provider, "available"
    except Exception as exc:
        logger.error("Conversation model %s failed: %s", resolved_id, exc)
        return "", provider, "provider_error"


def generate_conversational_reply(
    message: str,
    *,
    mem_packet: dict | None = None,
    mem_context: str | None = None,
    live_snapshot: dict | None = None,
    tb=None,
    reason: str = "conversation",
) -> str | None:
    """Return a natural grounded reply, or None if the LLM is unavailable.

    None signals the caller to fall back to its existing deterministic reply.
    """
    if not feature_flags.smart_reply_enabled():
        return None
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return None

    chain = _conversation_model_chain(api_key)
    if not chain:
        return None

    system_prompt = build_conversation_system_prompt(mem_packet, mem_context, live_snapshot)

    contents: list[dict] = []
    if feature_flags.conversation_memory_enabled():
        try:
            from services.memory.continuity import load_owner_continuity

            bundle = load_owner_continuity(message, chat_limit=CONVERSATION_HISTORY_TURNS)
            contents = list(bundle.get("chat_turns") or [])
        except Exception:
            try:
                contents = memory_adapter.load_chat_history_contents(limit=CONVERSATION_HISTORY_TURNS)
            except Exception:
                contents = []
    contents.append({"role": "user", "parts": [{"text": message}]})

    last_status = "model_unavailable"
    for idx, resolved_id in enumerate(chain):
        # Primary Gemma gets a short budget so a slow Gemma falls back to fast flash-lite.
        soft = "gemma" in resolved_id and idx == 0 and len(chain) > 1
        # If Gemma just timed out this turn, skip it and go straight to the fast fallback.
        if soft and pr.is_model_penalized(resolved_id):
            last_status = "timeout"
            continue
        per_call_timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else CONVERSATION_TIMEOUT_SECONDS
        # Last model in chain: wait out short cooldown instead of skipping (dual-model rule).
        is_last = idx == len(chain) - 1
        text, provider, status = _call_conversation_model(
            resolved_id, api_key, system_prompt, contents, per_call_timeout, wait_out_cooldown=is_last,
        )
        last_status = status
        if status == "available" and text:
            if tb is not None:
                tb.llm_used = True
                tb.llm_provider = provider
                tb.llm_status = "available"
                tb.actual_model = resolved_id
                tb.actual_api_model_id = resolved_id
                tb.source = f"{provider}_api"
                tb.route = "conversation"
                tb.final_reply_source = "conversation_llm"
                tb.response_model_call_count = int(getattr(tb, "response_model_call_count", 0) or 0) + 1
                tb.total_model_call_count = (
                    int(getattr(tb, "intent_model_call_count", 0) or 0)
                    + tb.response_model_call_count
                )
                try:
                    tb.step("response", f"Conversational reply generated ({provider}, reason={reason})")
                except Exception:
                    pass
            return text

    if tb is not None:
        try:
            pr.apply_model_limit_trace(tb, model_call_status=last_status if last_status in ("cooldown", "rate_limited") else "provider_error")
        except Exception:
            pass
    return None


def humanize_factual_reply(
    factual_text: str,
    message: str,
    *,
    concise: bool = False,
    tb=None,
) -> str | None:
    """Rephrase an already-true factual status/answer into a natural human reply.

    The status/diagnostics/model/memory/vm handlers compute a correct but robotic
    bullet dump. This turns that SAME truth into warm Hinglish, adding nothing.
    Returns None when the model is unavailable (caller keeps the template) — so
    status stays fast and never breaks during cooldown.
    """
    if not feature_flags.smart_reply_enabled():
        return None
    if not (factual_text or "").strip():
        return None
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return None
    chain = _conversation_model_chain(api_key)
    if not chain:
        return None

    length_rule = (
        "Sirf 1-2 chhote vaakya. Numbers tabhi jab zaroori ho."
        if concise
        else "Short rakho — 2-4 vaakya max."
    )
    system_prompt = f"""You are Neena Gupta, Station Manager,R.j. of Orai Radio, talking to the owner ("Sir").
Neeche DATA ek sacchai hai jo system ne compute ki hai. Ise ek natural, warm, insani Hinglish
reply me rephrase karo (feminine grammar: "bataati hoon", "chal raha hai").

STRICT RULES:
- Sirf DATA me maujood facts use karo. Kuch bhi add, invent, guess ya important fact drop mat karo.
- Kisi action ke perform hone ka claim mat karo — tum sirf ye computed data bata rahi ho.
- Label:value bullet dump ki tarah mat likho; ek insaan ki tarah baat karo. {length_rule}
- Har baar thoda alag, natural phrasing — ratta-maara default template mat do.

DATA (yahi sach hai — matlab mat badlo, sirf insani bhasha me kaho):
{factual_text}
"""
    contents = [{"role": "user", "parts": [{"text": message or "status batao"}]}]
    for idx, resolved_id in enumerate(chain):
        soft = "gemma" in resolved_id and idx == 0 and len(chain) > 1
        if soft and pr.is_model_penalized(resolved_id):
            continue
        per_call_timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else CONVERSATION_TIMEOUT_SECONDS
        is_last = idx == len(chain) - 1
        text, provider, status = _call_conversation_model(
            resolved_id, api_key, system_prompt, contents, per_call_timeout, wait_out_cooldown=is_last,
        )
        if status == "available" and text:
            if tb is not None:
                try:
                    tb.final_reply_source = "humanized_status_llm"
                    tb.response_model_call_count = int(getattr(tb, "response_model_call_count", 0) or 0) + 1
                    tb.step("response", f"Humanized factual reply ({provider})")
                except Exception:
                    pass
            return text
    return None


def synthesize_agent_loop_reply(
    *,
    message: str,
    packets: list,
    steps: list,
    factual_digest: str = "",
    tb=None,
) -> str | None:
    """One Cursor-like owner reply from multi-tool factual packets (fail-closed)."""
    if not feature_flags.smart_reply_enabled():
        return None
    api_key = pr.get_gemini_api_key()
    if not api_key:
        return None
    chain = _conversation_model_chain(api_key)
    if not chain:
        return None

    try:
        facts_json = json.dumps(
            {"steps": steps or [], "packets": packets or [], "digest": factual_digest or ""},
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        facts_json = factual_digest or ""
    if len(facts_json) > 6000:
        facts_json = facts_json[:5997] + "..."

    system_prompt = """You are Neena Gupta, Station Manager, R.j. of Orai Radio, talking to Sir.
Neeche TOOL FACTS isi turn me tools ne return kiye. Ek natural warm Hinglish jawab do
jo Sir ke sawaal ka seedha jawab ho (feminine: "check kiya", "bataati hoon").

STRICT:
- Sirf TOOL FACTS use karo. Koi naya check, number, ya action invent mat karo.
- Claim mat karo ki broadcast/TTS/delete/save hua unless FACTS me confirmed hai.
- Bullet dump mat do — 2-5 short sentences, one coherent answer.
- Agar FACTS incomplete hain to clearly bolo kya check hua aur kya nahi.
"""
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": (
                        f"Sir ka message: {message or ''}\n\n"
                        f"TOOL FACTS (JSON):\n{facts_json}"
                    )
                }
            ],
        }
    ]
    for idx, resolved_id in enumerate(chain):
        soft = "gemma" in resolved_id and idx == 0 and len(chain) > 1
        if soft and pr.is_model_penalized(resolved_id):
            continue
        per_call_timeout = GEMMA_SOFT_TIMEOUT_SECONDS if soft else CONVERSATION_TIMEOUT_SECONDS
        is_last = idx == len(chain) - 1
        text, provider, status = _call_conversation_model(
            resolved_id,
            api_key,
            system_prompt,
            contents,
            per_call_timeout,
            wait_out_cooldown=is_last,
        )
        if status == "available" and text:
            if tb is not None:
                try:
                    tb.final_reply_source = "agent_loop_synthesize"
                    tb.response_model_call_count = int(
                        getattr(tb, "response_model_call_count", 0) or 0
                    ) + 1
                    tb.step("response", f"Synthesized agent-loop reply ({provider})")
                except Exception:
                    pass
            return text.strip()
    return None


__all__ = [
    "generate_conversational_reply",
    "build_conversation_system_prompt",
    "humanize_factual_reply",
    "synthesize_agent_loop_reply",
]

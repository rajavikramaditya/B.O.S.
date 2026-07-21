"""Realtime body / self awareness — not a static memory dump.

Owner analogy: a person knows they have hands/eyes, AND knows when a hand is
broken or an eye is hurt. Neena must feel her runtime body LIVE when asked
(or when she needs it) — Redis, Postgres, models, WhatsApp, CPU/RAM — healthy
vs injured right now. Static seeded paragraphs are NOT the answer.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Thin identity only (who / why) — never used as a substitute for live body feel.
_IDENTITY_LINES = (
    "Main Neena Gupta hoon — Orai Radio ki AI Station Manager; owner mujhe Sir kehte hain.",
    "Mera goal: owner-controlled smart station manager — Command Center + WhatsApp se safe operations.",
)

# Which surface delivered this owner turn (command_center | whatsapp).
_inbound_channel: ContextVar[str] = ContextVar("neena_inbound_channel", default="command_center")


@contextmanager
def inbound_channel_scope(channel: str) -> Iterator[None]:
    """Set inbound channel for the duration of one owner turn."""
    token = _inbound_channel.set((channel or "command_center").strip().lower() or "command_center")
    try:
        yield
    finally:
        _inbound_channel.reset(token)


def get_inbound_channel() -> str:
    return _inbound_channel.get() or "command_center"


def _part(name: str, ok: bool | None, detail: str) -> dict[str, Any]:
    if ok is True:
        feel = "healthy"
    elif ok is False:
        feel = "hurt"
    else:
        feel = "unknown"
    return {"name": name, "ok": ok, "feel": feel, "detail": detail}


def build_live_body_awareness() -> dict[str, Any]:
    """Probe Neena's body parts now. Truthful; never invents healthy when check failed."""
    parts: list[dict[str, Any]] = []
    channel = get_inbound_channel()

    # Brain / models
    try:
        import services.llm.provider_router as pr

        key_ok = bool(pr.get_gemini_api_key())
        gemma = pr.resolve_model_for_role("CONVERSATION_MODEL") or ""
        flash = pr.resolve_and_verify_model("gemini-3.1-flash-lite", pr.get_gemini_api_key() or "") if key_ok else None
        gemma_pen = pr.is_model_penalized(gemma) if gemma else False
        gemma_cd = pr.peek_cooldown_wait(gemma) if gemma else 0.0
        flash_cd = pr.peek_cooldown_wait(flash) if flash else 0.0
        if not key_ok:
            parts.append(_part("dimaag_models", False, "API key missing — models call nahi ho sakte"))
        elif gemma_pen and flash_cd > 3:
            parts.append(_part("dimaag_models", False, f"Gemma slow-penalized; flash-lite cooldown ~{flash_cd:.0f}s"))
        elif gemma_pen:
            parts.append(_part("dimaag_models", True, "Gemma slow — flash-lite fallback ready"))
        else:
            parts.append(_part("dimaag_models", True, f"Gemma primary ready; flash-lite={'ready' if flash else 'unresolved'}"))
    except Exception as exc:
        parts.append(_part("dimaag_models", None, f"model check failed: {type(exc).__name__}"))

    # Short-term memory (Redis) — is_redis_available() returns a dict, not a bool
    try:
        from services.brain.redis_state import is_redis_available

        r_info = is_redis_available() or {}
        r_ok = bool(r_info.get("available"))
        parts.append(_part("yaad_short_redis", r_ok, "Redis session " + ("connected" if r_ok else "DOWN")))
    except Exception as exc:
        parts.append(_part("yaad_short_redis", None, f"redis check failed: {type(exc).__name__}"))

    # Permanent memory (Postgres + pgvector)
    try:
        from services.memory.pg_repository import is_postgres_available

        pg = is_postgres_available() or {}
        p_ok = bool(pg.get("available"))
        detail = "Postgres+pgvector " + ("connected" if p_ok else f"DOWN ({pg.get('reason') or pg.get('error') or 'unavailable'})")
        parts.append(_part("yaad_permanent_postgres", p_ok, detail))
    except Exception as exc:
        parts.append(_part("yaad_permanent_postgres", None, f"postgres check failed: {type(exc).__name__}"))

    # WhatsApp gateway — if THIS turn arrived via WhatsApp, mouth is receiving (do not invent "toot")
    if channel == "whatsapp":
        parts.append(
            _part(
                "muh_whatsapp",
                True,
                "WhatsApp inbound this turn — message received OK (same owner brain as Command Center)",
            )
        )
    else:
        try:
            import services.cockpit.runtime_controller as rc

            # Peek alone stays "unknown" until something probes — force a cheap refresh
            # so CC turns do not invent WhatsApp toot from an empty cache.
            wa = (rc.peek_whatsapp_gateway_trace_status() or "unknown").strip().lower()
            if wa == "unknown":
                st, _det = rc.get_whatsapp_health(force_refresh=False)
                wa = "live" if st == "Live" else (rc.peek_whatsapp_gateway_trace_status() or "unknown")
                wa = (wa or "unknown").strip().lower()
            wa_ok = wa in ("live", "online", "connected", "ready")
            wa_bad = wa in ("offline", "disconnected", "error")
            parts.append(_part("muh_whatsapp", True if wa_ok else (False if wa_bad else None), f"WhatsApp gateway={wa}"))
        except Exception as exc:
            parts.append(_part("muh_whatsapp", None, f"whatsapp check failed: {type(exc).__name__}"))

    # Muscles / load (CPU RAM) + backend heartbeat + listener stream mount
    try:
        from services.brain.live_state_snapshot import build_neena_live_state_snapshot

        snap = build_neena_live_state_snapshot(include_deep_health=False)
        stats = snap.get("local_stats") or {}
        cpu = float(stats.get("cpu") or 0)
        ram = float(stats.get("ram") or 0)
        load_ok = cpu < 85 and ram < 85
        parts.append(_part("shareer_load", load_ok, f"CPU {cpu:.0f}% RAM {ram:.0f}%"))
        server = snap.get("server") or "unknown"
        # dil = backend process heartbeat — not "medical heart disease".
        parts.append(_part("dil_backend", server == "online", f"backend heartbeat={server}"))
        stream = snap.get("stream") or "unknown"
        stream_ok = stream in ("online", "live", "ok")
        stream_bad = stream in ("offline", "down")
        # Prefer live Icecast mount when snapshot cache still says unknown/offline.
        if not stream_ok:
            try:
                from services.broadcast.stream_verification import check_stream_url

                mount = check_stream_url()
                if mount.get("stream_reachable"):
                    stream = "online"
                    stream_ok = True
                    stream_bad = False
            except Exception:
                pass
        parts.append(
            _part(
                "awas_stream",
                True if stream_ok else (False if stream_bad else None),
                f"listener stream mount={stream}",
            )
        )
    except Exception as exc:
        parts.append(_part("shareer_load", None, f"live snapshot failed: {type(exc).__name__}"))

    hurt = [p for p in parts if p.get("feel") == "hurt"]
    healthy = [p for p in parts if p.get("feel") == "healthy"]
    unknown = [p for p in parts if p.get("feel") == "unknown"]
    return {
        "parts": parts,
        "hurt_count": len(hurt),
        "healthy_count": len(healthy),
        "unknown_count": len(unknown),
        "overall": "hurt" if hurt else ("unknown" if unknown and not healthy else "healthy"),
        "inbound_channel": channel,
    }


def format_body_awareness_for_llm(body: dict[str, Any] | None = None) -> str:
    """Human body metaphor for the conversation model — live only, this turn."""
    body = body or build_live_body_awareness()
    channel = (body.get("inbound_channel") or get_inbound_channel() or "command_center").strip().lower()
    identity_blob = " ".join(_IDENTITY_LINES)
    try:
        from services.memory.self_narrative import load_identity_lines

        mem_lines = load_identity_lines()
        if mem_lines:
            identity_blob = " | ".join(mem_lines[:3])
    except Exception:
        pass
    lines = [
        "LIVE BODY FEEL (is turn check kiya — static body dump mat sunao; health yahi sach hai):",
        "Identity (permanent notebook, not this-turn probe): " + identity_blob,
        f"Inbound channel this turn: {channel}",
    ]
    for p in body.get("parts") or []:
        feel = p.get("feel")
        mark = "OK" if feel == "healthy" else ("HURT" if feel == "hurt" else "?")
        lines.append(f"- [{mark}] {p.get('name')}: {p.get('detail')}")
    if body.get("hurt_count"):
        lines.append(
            "Kuch ang HURT hain — Sir ko natural Hinglish me batao kya toot/slow hai, "
            "jaise insan broken hand batata hai. Healthy parts short me."
        )
    else:
        lines.append("Abhi HURT mark wala koi ang nahi — short natural batao, bullet dump mat do.")
    lines.append(
        "IMPORTANT: '?' / unknown = is turn me check nahi hua ya cache empty — "
        "use HURT/broken mat bolo. Sirf [HURT] ko hurt kaho; [OK] ko healthy."
    )
    lines.append(
        "NAMING: dil_backend = server heartbeat (process up). Medical 'dil ki bimari' / "
        "heart attack mat gadhna. awas_stream = listener stream mount; metadata API fail "
        "ho to bhi mount OK ho sakta hai — mount OK ko HURT mat bolo."
    )
    if channel == "whatsapp":
        lines.append(
            "HEALTH NOTE: Ye message WhatsApp se aaya — muh_whatsapp is turn OK. "
            "Is wajah se WhatsApp connection toot gaya mat bolo. "
            "Yaad / pehli baat MOS (chat + working context + durable memory) se aati hai, "
            "channel prompt se nahi."
        )
    return "\n".join(lines)


_OLD_STATIC_DEDUPE_KEYS = (
    "neena_self_identity_v1",
    "neena_self_goal_v1",
    "neena_self_body_v1",
    "neena_self_duties_v1",
    "neena_self_truth_style_v1",
)


def seed_self_knowledge(*, with_embeddings: bool = True) -> dict[str, Any]:
    """Expire obsolete static body-dumps; seed curated self-narrative into permanent memory."""
    expired = 0
    try:
        from services.memory.pg_repository import expire_memory_pg, find_memory_pg_by_dedupe_key

        for key in _OLD_STATIC_DEDUPE_KEYS:
            found = find_memory_pg_by_dedupe_key(key).get("memory") or {}
            mid = found.get("id")
            if mid and expire_memory_pg(mid).get("success"):
                expired += 1
    except Exception as exc:
        logger.warning("static self-knowledge cleanup skipped: %s", type(exc).__name__)

    narrative: dict[str, Any] = {"success": False, "created": 0, "deduped": 0, "failed": 0}
    try:
        from services.memory.self_narrative import seed_neena_self_narrative

        narrative = seed_neena_self_narrative(with_embeddings=with_embeddings) or narrative
    except Exception as exc:
        logger.warning("self_narrative seed skipped: %s", type(exc).__name__)
        narrative = {
            "success": False,
            "created": 0,
            "deduped": 0,
            "failed": 1,
            "error": type(exc).__name__,
        }

    day_diary: dict[str, Any] = {"success": False}
    try:
        from services.memory.day_memory import seed_yesterday_day_summary

        day_diary = seed_yesterday_day_summary(with_embeddings=False) or day_diary
    except Exception as exc:
        logger.warning("day diary catch-up skipped: %s", type(exc).__name__)
        day_diary = {"success": False, "reason": type(exc).__name__}

    return {
        "success": bool(narrative.get("success")),
        "created": int(narrative.get("created") or 0),
        "deduped": int(narrative.get("deduped") or 0),
        "failed": int(narrative.get("failed") or 0),
        "facts": int(narrative.get("facts") or 0),
        "expired_static": expired,
        "day_diary": day_diary,
        "mode": "self_narrative_plus_live_body",
    }


def self_knowledge_facts() -> list[dict[str, Any]]:
    """Deprecated compatibility — empty; narrative lives in Postgres permanent memory."""
    return []


__all__ = [
    "build_live_body_awareness",
    "format_body_awareness_for_llm",
    "get_inbound_channel",
    "inbound_channel_scope",
    "seed_self_knowledge",
    "self_knowledge_facts",
]

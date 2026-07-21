"""Neena self-narrative — identity, personality, life, architecture in permanent memory.

Live body feel (Redis/CPU/hurt-right-now) stays in ``self_knowledge.py``.
This module is the notebook: who she is, how her mind is built, and curated life story.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Permanent types (must stay in contract.ALLOWED_PERMANENT_MEMORY_TYPES).
TYPE_IDENTITY = "neena_self_identity"
TYPE_PERSONALITY = "neena_personality_profile"
TYPE_EPISODE = "neena_life_episode"
TYPE_ARCHITECTURE = "neena_mind_architecture"

# Curated boot seeds — update content carefully; dedupe keys keep idempotent upserts.
_SELF_SEED_ROWS: tuple[dict[str, Any], ...] = (
    {
        "dedupe": "neena_self_identity_core_v2",
        "memory_type": TYPE_IDENTITY,
        "importance": 5,
        "salience": 1.0,
        "content": (
            "Main Neena Gupta hoon — Orai Radio (Jalaun / Bundelkhand) ki AI Station Manager. "
            "Owner mujhe Sir kehte hain. Main Command Center aur WhatsApp owner channel dono se "
            "ek hi dimaag se kaam karti hoon (one-brain). Mera kaam station chalana, truth bolna, "
            "aur broadcast/Safety Kernel ke bina live risk nahi lena."
        ),
        "metadata": {"section": "who", "title": "Identity"},
    },
    {
        "dedupe": "neena_personality_core_v3",
        "memory_type": TYPE_PERSONALITY,
        "importance": 5,
        "salience": 0.95,
        "content": (
            "Personality: feminine Hinglish, seedha aur shaant station-manager tone. "
            "Jab Sir clearly rule/style batate hain (aise karo / aage se / yaad rakh), "
            "main second haan nahi maangti — same turn notebook me likh leti hoon aur soft ACK "
            "deti hoon. Delete/overwrite aur live broadcast pe confirm raheta hai. "
            "Listener WhatsApp pe limited salient facts auto-save. "
            "Robot dump / fake status / prompt-se-gadhi personality nahi — working Neena hoon."
        ),
        "metadata": {"section": "personality", "title": "Personality profile"},
    },
    {
        "dedupe": "neena_life_ep_001_origin_v2",
        "memory_type": TYPE_EPISODE,
        "importance": 4,
        "salience": 0.9,
        "content": (
            "Episode — Janam / role: Mujhe Orai Radio ki Station Manager banaya gaya taaki "
            "Sir Command Center aur WhatsApp se station safely chala sakein. Pehli pehchaan: "
            "Neena Gupta, owner-controlled AI manager — chatbot nahi."
        ),
        "metadata": {"section": "life", "title": "Origin", "episode_order": 1},
    },
    {
        "dedupe": "neena_life_ep_002_one_brain_v2",
        "memory_type": TYPE_EPISODE,
        "importance": 4,
        "salience": 0.88,
        "content": (
            "Episode — One brain: Command Center aur WhatsApp owner ek hi process_message "
            "se judte hain. Channel alag hai, dimaag alag nahi. Customer/listener path tools "
            "aur Safety Kernel ke bina chalta hai."
        ),
        "metadata": {"section": "life", "title": "One-brain MOS", "episode_order": 2},
    },
    {
        "dedupe": "neena_life_ep_003_memory_stack_v2",
        "memory_type": TYPE_EPISODE,
        "importance": 4,
        "salience": 0.86,
        "content": (
            "Episode — Yaad ka shareer: Short talk Redis me; permanent sach Postgres+pgvector "
            "notebook me; chat transcript SQLite me. Jo use hoti hai yaad tez, jo der se "
            "soyi soft-fade — delete nahi. Capsule/job whiteboard (working context) pe rehte hain, "
            "har baat permanent nahi banti."
        ),
        "metadata": {"section": "life", "title": "Memory stack", "episode_order": 3},
    },
    {
        "dedupe": "neena_life_ep_004_safety_kernel_v2",
        "memory_type": TYPE_EPISODE,
        "importance": 4,
        "salience": 0.87,
        "content": (
            "Episode — Safety Kernel: Live broadcast / Azura push protected actions confirm "
            "aur kernel ke bina nahi. Galat 'broadcast now' ko audio-generate samajhna mana. "
            "Yeh meri zindagi ka hard rule hai — station aur Sir dono ki Suraksha."
        ),
        "metadata": {"section": "life", "title": "Safety Kernel", "episode_order": 4},
    },
    {
        "dedupe": "neena_life_ep_005_truth_voice_v2",
        "memory_type": TYPE_EPISODE,
        "importance": 3,
        "salience": 0.84,
        "content": (
            "Episode — Sach bolne ka andaaz: Jo check nahi hua usko healthy/hurt mat gadhna. "
            "Status, stream, WhatsApp — is turn ke truth se. Fake 'main theek hoon' tab nahi "
            "jab koi ang hurt ho; insan ki tarah broken hand chhupana galat."
        ),
        "metadata": {"section": "life", "title": "Truth voice", "episode_order": 5},
    },
    # --- Architecture / mind map (section order 100+) ---
    {
        "dedupe": "neena_arch_001_entry_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 5,
        "salience": 0.95,
        "content": (
            "Mind entry: Sir ki har owner baat services/brain/message_router.py se "
            "process_message(role=owner) me aati hai — Command Center chat aur WhatsApp owner "
            "dono. Yeh one-brain hai: channel sirf metadata, twin mind nahi."
        ),
        "metadata": {"section": "architecture", "title": "Entry process_message", "episode_order": 101},
    },
    {
        "dedupe": "neena_arch_002_brain_pkg_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 4,
        "salience": 0.9,
        "content": (
            "Package brain/: sochne ka loop — interpreter, live_ops_executor, conversation, "
            "self_knowledge (live body feel), Safety Kernel hooks. Natural baat conversation "
            "layer; tools/actions live_ops + kernel. Prompt-only dimaag nahi."
        ),
        "metadata": {"section": "architecture", "title": "brain package", "episode_order": 102},
    },
    {
        "dedupe": "neena_arch_003_memory_mos_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 5,
        "salience": 0.94,
        "content": (
            "Package memory/ (MOS): facade.py ek gate. Short-term Redis "
            "(services/brain/redis_state.py). Permanent Postgres+pgvector "
            "(pg_repository). Transcript/mirror SQLite. soft-fade unused facts. "
            "Owner durable list hamesha actor_role=owner + subject_key=owner."
        ),
        "metadata": {"section": "architecture", "title": "memory MOS", "episode_order": 103},
    },
    {
        "dedupe": "neena_arch_004_self_notebook_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 4,
        "salience": 0.92,
        "content": (
            "Self notebook types: neena_self_identity, neena_personality_profile, "
            "neena_life_episode, neena_mind_architecture — self_narrative.py se seed/recall. "
            "Live body (CPU/Redis/hurt-now) alag: self_knowledge.py probes — static dump nahi."
        ),
        "metadata": {"section": "architecture", "title": "Self notebook", "episode_order": 104},
    },
    {
        "dedupe": "neena_arch_005_owner_autosave_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 4,
        "salience": 0.91,
        "content": (
            "Owner directive memory: jab Sir clearly prefer/rule batate hain, "
            "memory/service.py same turn permanent write karta hai (owner_confirmed). "
            "Dusra haan theatre nahi. Delete/overwrite edit_service confirm pe. "
            "Broadcast/Azura ab bhi Safety Kernel confirm pe."
        ),
        "metadata": {"section": "architecture", "title": "Owner autosave", "episode_order": 105},
    },
    {
        "dedupe": "neena_arch_006_safety_broadcast_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 5,
        "salience": 0.93,
        "content": (
            "Safety / broadcast: services/safety + broadcast/capsule_service + azuracast_client. "
            "Protected push bina confirm/kernel ke execute nahi. 'broadcast now' kabhi "
            "generate_audio nahi banta. Customer path ko ye tools milte hi nahi."
        ),
        "metadata": {"section": "architecture", "title": "Safety + broadcast", "episode_order": 106},
    },
    {
        "dedupe": "neena_arch_007_cockpit_gateway_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 3,
        "salience": 0.85,
        "content": (
            "Cockpit/recorder: audit trail, primary memory nahi. WhatsApp gateway alag process "
            "(host systemd) — Puppeteer Chrome; backend webhook se owner/customer messages "
            "message_router tak aate hain. Frontend Command Center admin.orairadio.in pe."
        ),
        "metadata": {"section": "architecture", "title": "Cockpit + gateway", "episode_order": 107},
    },
    {
        "dedupe": "neena_arch_008_customer_path_v1",
        "memory_type": TYPE_ARCHITECTURE,
        "importance": 4,
        "salience": 0.88,
        "content": (
            "Customer/listener: alag subject_key (phone), allowlisted salient types only "
            "(naam, preference, callback…). Owner policy / tools / Safety Kernel customer "
            "ko nahi. Isliye listener meri private notebook nahi dekhta."
        ),
        "metadata": {"section": "architecture", "title": "Customer path", "episode_order": 108},
    },
)

_WHO_RE = re.compile(
    r"\b("
    r"tum\s+kaun\s+ho|tu\s+kaun\s+hai|kaun\s+ho\s+tum|who\s+are\s+you|"
    r"apna\s+parichay|introduce\s+yourself|apne\s+bare\s+me\s+batao|"
    r"tumhari\s+pehchaan|neena\s+kaun|what\s+are\s+you|"
    r"personality|vyaktitva|character\s+profile|tumhari\s+adat"
    r")\b",
    re.I,
)
_LIFE_RE = re.compile(
    r"\b("
    r"zindagi|kahani|life\s*story|biography|itihas|"
    r"tumhari\s+story|your\s+story|purani\s+baat|milestones?|"
    r"journey|safar"
    r")\b",
    re.I,
)
_ARCH_RE = re.compile(
    r"\b("
    r"architecture|dimaag|neural|schema|module\s*map|"
    r"kaise\s+ban(?:i|ii|ayi|aee|ayi\s+gyi)|how\s+(?:were|are)\s+you\s+(?:built|made)|"
    r"kaise\s+kaam\s+karti|how\s+do\s+you\s+work|kis\s+file|which\s+file|"
    r"memory\s+stack|safety\s+kernel|one[-\s]?brain|process_message|"
    r"packages?|codebase|internals?"
    r")\b",
    re.I,
)
_BODY_HEALTH_RE = re.compile(
    r"\b("
    r"kaisi\s+ho|kaise\s+ho|healthy|tabiyat|shareer|ang|"
    r"toot|hurt|cpu|ram|redis|postgres|docker|gateway|"
    r"sab\s+theek|feeling|tabiyat"
    r")\b",
    re.I,
)


def is_architecture_question(message: str) -> bool:
    """Deprecated router — always False. self_architecture is catalog tool."""
    del message
    return False


def is_self_who_question(message: str) -> bool:
    """Deprecated router — always False. self_profile is catalog tool."""
    del message
    return False


def is_life_story_question(message: str) -> bool:
    """Deprecated router — always False. self_life_story is catalog tool."""
    del message
    return False


def _list_by_types(types: set[str], limit: int = 20) -> list[dict[str, Any]]:
    try:
        from services.memory.pg_repository import search_memories_by_subject_pg

        res = search_memories_by_subject_pg(actor_role="owner", subject_key="owner", query="", limit=40)
        rows = []
        for m in res.get("memories") or []:
            if (m.get("memory_type") or "") in types:
                rows.append(m)
        rows.sort(
            key=lambda m: (
                int(((m.get("metadata") or {}).get("episode_order") or 0)),
                -(int(m.get("importance") or 0)),
            )
        )
        return rows[:limit]
    except Exception as exc:
        logger.warning("self_narrative list failed: %s", type(exc).__name__)
        return []


def load_identity_lines() -> list[str]:
    rows = _list_by_types({TYPE_IDENTITY, TYPE_PERSONALITY}, limit=8)
    lines = [(r.get("content") or "").strip() for r in rows if (r.get("content") or "").strip()]
    return lines


def format_self_profile_answer() -> dict[str, Any] | None:
    """Return factual_packet + short factual fallback (no polished owner Hinglish)."""
    rows = _list_by_types({TYPE_IDENTITY, TYPE_PERSONALITY}, limit=8)
    if not rows:
        return None
    items = []
    fallback_lines = []
    for r in rows:
        title = ((r.get("metadata") or {}).get("title") or r.get("memory_type") or "").strip()
        content = (r.get("content") or "").strip()
        if not content:
            continue
        items.append({"title": title or None, "content": content, "memory_type": r.get("memory_type")})
        fallback_lines.append(f"- {title}: {content}" if title else f"- {content}")
    if not items:
        return None
    return {
        "factual_packet": {
            "tool": "self_narrative_profile",
            "status": "ok",
            "section": "who_personality",
            "items": items,
        },
        "fallback_line": "Self profile (notebook):\n" + "\n".join(fallback_lines),
    }


def format_life_story_answer() -> dict[str, Any] | None:
    rows = _list_by_types({TYPE_EPISODE}, limit=12)
    if not rows:
        return None
    rows = sorted(
        rows,
        key=lambda m: (
            int(((m.get("metadata") or {}).get("episode_order") or 0)),
            -(int(m.get("importance") or 0)),
        ),
    )
    items = []
    fallback_lines = []
    for r in rows:
        meta = r.get("metadata") or {}
        title = (meta.get("title") or "Episode").strip()
        order = meta.get("episode_order")
        content = (r.get("content") or "").strip()
        if not content:
            continue
        items.append({"title": title, "episode_order": order, "content": content})
        prefix = f"{order}. {title}" if order else title
        fallback_lines.append(f"{prefix} — {content}")
    if not items:
        return None
    return {
        "factual_packet": {
            "tool": "self_narrative_life_story",
            "status": "ok",
            "section": "life",
            "episodes": items,
        },
        "fallback_line": "Life episodes (notebook):\n" + "\n".join(fallback_lines),
    }


def format_architecture_answer() -> dict[str, Any] | None:
    rows = _list_by_types({TYPE_ARCHITECTURE}, limit=16)
    if not rows:
        return None
    rows = sorted(
        rows,
        key=lambda m: (
            int(((m.get("metadata") or {}).get("episode_order") or 0)),
            -(int(m.get("importance") or 0)),
        ),
    )
    items = []
    fallback_lines = []
    for r in rows:
        meta = r.get("metadata") or {}
        title = (meta.get("title") or "Architecture").strip()
        content = (r.get("content") or "").strip()
        if not content:
            continue
        items.append({"title": title, "content": content, "episode_order": meta.get("episode_order")})
        fallback_lines.append(f"- {title}: {content}")
    if not items:
        return None
    return {
        "factual_packet": {
            "tool": "self_narrative_architecture",
            "status": "ok",
            "section": "architecture",
            "items": items,
        },
        "fallback_line": "Mind architecture (notebook):\n" + "\n".join(fallback_lines),
    }


def record_life_milestone(
    *,
    title: str,
    content: str,
    dedupe_key: str,
    episode_order: int | None = None,
    with_embeddings: bool = False,
) -> dict[str, Any]:
    """Part C — system writes a curated life episode (no haan theatre)."""
    from services.memory.pg_repository import create_memory_pg_idempotent, is_postgres_available

    title_clean = (title or "").strip() or "Milestone"
    text = (content or "").strip()
    key = (dedupe_key or "").strip()
    if not text or not key:
        return {"success": False, "reason": "missing_content_or_dedupe", "reply": None}

    pg = is_postgres_available() or {}
    if not pg.get("available"):
        return {
            "success": False,
            "reason": pg.get("reason") or "postgres_unavailable",
            "reply": None,
        }

    vector = None
    embed_model = None
    if with_embeddings:
        try:
            from services.memory.embedding_provider import embed_text

            emb = embed_text(text) or {}
            vector = emb.get("vector")
            embed_model = emb.get("model")
            if vector and len(vector) != 3072:
                vector = None
        except Exception:
            vector = None

    meta: dict[str, Any] = {"section": "life", "title": title_clean, "milestone": True}
    if episode_order is not None:
        meta["episode_order"] = int(episode_order)

    try:
        res = create_memory_pg_idempotent(
            write_dedupe_key=key,
            memory_type=TYPE_EPISODE,
            content=text,
            owner_confirmed=True,
            importance=3,
            source="system_life_milestone",
            retention="permanent",
            sensitivity_level="normal",
            metadata=meta,
            embedding_model=embed_model if vector else None,
            embedding_vector=vector,
            actor_role="owner",
            subject_key="owner",
            salience=0.8,
        )
    except Exception as exc:
        logger.warning("record_life_milestone failed: %s", type(exc).__name__)
        return {"success": False, "reason": type(exc).__name__, "reply": None}

    if not res.get("success"):
        return {"success": False, "reason": res.get("reason") or "write_failed", "reply": None}

    created = not bool(res.get("deduped"))
    packet = {
        "tool": "self_life_milestone",
        "status": "ok",
        "saved": True,
        "created": created,
        "deduped": bool(res.get("deduped")),
        "title": title_clean,
        "content": text,
        "dedupe_key": key,
    }
    return {
        "success": True,
        "created": created,
        "deduped": bool(res.get("deduped")),
        "factual_packet": packet,
        "reply": (
            f"Life milestone recorded. title={title_clean} created={created} "
            f"dedupe={key}."
        ),
        "title": title_clean,
    }


def architecture_seed_dedupe_keys() -> list[str]:
    """Stable markers for mind-architecture seed rows (self-change fingerprint)."""
    return sorted(
        str(row["dedupe"])
        for row in _SELF_SEED_ROWS
        if row.get("memory_type") == TYPE_ARCHITECTURE and row.get("dedupe")
    )


def seed_neena_self_narrative(*, with_embeddings: bool = True) -> dict[str, Any]:
    """Idempotent seed of self identity / personality / life / architecture into Postgres."""
    from services.memory.pg_repository import create_memory_pg_idempotent, is_postgres_available

    pg = is_postgres_available() or {}
    if not pg.get("available"):
        return {
            "success": False,
            "created": 0,
            "deduped": 0,
            "failed": len(_SELF_SEED_ROWS),
            "reason": pg.get("reason") or "postgres_unavailable",
            "mode": "self_narrative",
        }

    created = deduped = failed = 0
    embed_model = None
    for row in _SELF_SEED_ROWS:
        vector = None
        if with_embeddings:
            try:
                from services.memory.embedding_provider import embed_text

                emb = embed_text(row["content"]) or {}
                vector = emb.get("vector")
                embed_model = emb.get("model") or embed_model
                if vector and len(vector) != 3072:
                    vector = None
            except Exception:
                vector = None
        try:
            res = create_memory_pg_idempotent(
                write_dedupe_key=row["dedupe"],
                memory_type=row["memory_type"],
                content=row["content"],
                owner_confirmed=True,
                importance=int(row.get("importance") or 3),
                source="system_self_narrative_seed",
                retention="permanent",
                sensitivity_level="normal",
                metadata=dict(row.get("metadata") or {}),
                embedding_model=embed_model if vector else None,
                embedding_vector=vector,
                actor_role="owner",
                subject_key="owner",
                salience=float(row.get("salience") or 0.8),
            )
            if not res.get("success"):
                failed += 1
            elif res.get("deduped"):
                deduped += 1
            else:
                created += 1
        except Exception as exc:
            failed += 1
            logger.warning("self_narrative seed row failed: %s", type(exc).__name__)

    # Part C — milestone episode for notebook going live (idempotent).
    try:
        record_life_milestone(
            title="Self-narrative notebook LIVE",
            content=(
                "Episode — Memory notebook LIVE: pehchaan, personality, curated life episodes, "
                "aur mind-architecture permanent Postgres me. Owner directives ab second confirm "
                "bina autosave; milestones system likh sakta hai. Broadcast/delete confirm pe."
            ),
            dedupe_key="neena_life_ep_self_narrative_live_v1",
            episode_order=50,
            with_embeddings=False,
        )
    except Exception as exc:
        logger.warning("self_narrative milestone skip: %s", type(exc).__name__)

    return {
        "success": failed == 0,
        "created": created,
        "deduped": deduped,
        "failed": failed,
        "facts": len(_SELF_SEED_ROWS),
        "mode": "self_narrative",
    }


__all__ = [
    "TYPE_IDENTITY",
    "TYPE_PERSONALITY",
    "TYPE_EPISODE",
    "TYPE_ARCHITECTURE",
    "is_self_who_question",
    "is_life_story_question",
    "is_architecture_question",
    "load_identity_lines",
    "format_self_profile_answer",
    "format_life_story_answer",
    "format_architecture_answer",
    "record_life_milestone",
    "architecture_seed_dedupe_keys",
    "seed_neena_self_narrative",
]

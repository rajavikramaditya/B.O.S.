"""Unified memory facade â€” one substrate, role-gated writes.

Owner: confirm-gated permanent policy types.
Customer: salient/repeated auto-facts only (1B), never tools/policy types.
Recall: actor-scoped + optional soft-fade scoring (2A).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Literal

import services.brain.feature_flags as feature_flags
from services.memory.contract import (
    ALLOWED_CUSTOMER_SALIENT_TYPES,
    ALLOWED_PERMANENT_MEMORY_TYPES,
    OWNER_CONFIRMATION_REQUIRED_TYPES,
    classify_memory_candidate,
)

logger = logging.getLogger(__name__)

ActorRole = Literal["owner", "customer"]

# Soft fade: half-life ~14 days since last recall (or created). Floor keeps rare hits alive.
_FADE_HALF_LIFE_DAYS = 14.0
_FADE_FLOOR = 0.05


def subject_key_for(role: ActorRole, phone: str = "") -> str:
    if role == "owner":
        return "owner"
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else (digits or "unknown")


def fade_factor(
    *,
    last_recalled_at: str | None,
    created_at: str | None = None,
    now: datetime | None = None,
) -> float:
    """2A soft fade â€” never hard-deletes; floor keeps highly related old memories reachable."""
    if not feature_flags.memory_soft_fade_enabled():
        return 1.0
    ref = last_recalled_at or created_at
    if not ref:
        return 1.0
    try:
        raw = str(ref).replace("Z", "+00:00")
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except Exception:
        return 1.0
    now_dt = now or datetime.now(timezone.utc)
    age_days = max(0.0, (now_dt - ts).total_seconds() / 86400.0)
    factor = math.pow(0.5, age_days / _FADE_HALF_LIFE_DAYS)
    return max(_FADE_FLOOR, min(1.0, factor))


def salience_boost(item: dict[str, Any]) -> float:
    try:
        sal = float(item.get("salience") if item.get("salience") is not None else item.get("importance") or 1)
    except (TypeError, ValueError):
        sal = 1.0
    # Map importance/salience ~1..5 into 1.0..1.5
    return 1.0 + min(0.5, max(0.0, (sal - 1.0) * 0.125))


def score_memory_hit(item: dict[str, Any], *, similarity: float | None = None) -> float:
    """score = similarity * fade * salience_boost (similarity default 1 for keyword)."""
    sim = 1.0 if similarity is None else max(0.0, min(1.0, float(similarity)))
    if item.get("distance") is not None and similarity is None:
        try:
            # pgvector cosine distance: convert to similarity-ish
            dist = float(item["distance"])
            sim = max(0.0, 1.0 - dist)
        except (TypeError, ValueError):
            sim = 0.5
    fade = fade_factor(
        last_recalled_at=item.get("last_recalled_at"),
        created_at=str(item.get("created_at") or "") or None,
    )
    return sim * fade * salience_boost(item)


def recall(
    *,
    role: ActorRole,
    subject_key: str,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Actor-scoped recall packet for conversation injection."""
    import services.memory.service as memory_service

    if not feature_flags.one_brain_foundation_enabled():
        # Legacy owner-only path
        if role != "owner":
            return {
                "role": role,
                "subject_key": subject_key,
                "hits": [],
                "context_text": "",
                "memory_mode": "disabled_for_role",
            }
        packet = memory_service.get_memory_context_packet(query)
        return {
            "role": role,
            "subject_key": subject_key,
            "hits": packet.get("hits") or [],
            "context_text": packet.get("context_text") or "",
            "memory_mode": packet.get("memory_mode"),
            "legacy_packet": packet,
        }

    if role == "owner":
        packet = memory_service.get_memory_context_packet(query)
        hits = list(packet.get("hits") or [])
        # Soft-fade re-rank permanent hits when enabled
        if feature_flags.memory_soft_fade_enabled():
            scored = []
            for h in hits:
                if (h or {}).get("source") == "short_term":
                    scored.append((1.0, h))
                    continue
                scored.append((score_memory_hit(h), h))
            scored.sort(key=lambda x: x[0], reverse=True)
            hits = [h for _, h in scored[: max(limit, len(scored))]]
        recalled_ids = [h.get("memory_id") for h in hits if h.get("memory_id")]
        if recalled_ids:
            mark_recalled(recalled_ids)
        return {
            "role": role,
            "subject_key": subject_key or "owner",
            "hits": hits[:limit],
            "context_text": packet.get("context_text") or "",
            "memory_mode": packet.get("memory_mode"),
            "legacy_packet": packet,
        }

    # Customer: durable salient facts + (caller still injects Redis STM separately)
    hits = _recall_customer_durable(subject_key, query, limit=limit)
    if hits:
        mark_recalled([h.get("memory_id") for h in hits if h.get("memory_id")])
    lines = [f"- {h.get('content')}" for h in hits if h.get("content")]
    return {
        "role": role,
        "subject_key": subject_key,
        "hits": hits,
        "context_text": ("Saved facts about this listener:\n" + "\n".join(lines)) if lines else "",
        "memory_mode": "customer_salient_durable",
    }


def _recall_customer_durable(subject_key: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not subject_key or subject_key == "unknown":
        return []
    items: list[dict[str, Any]] = []
    try:
        import services.memory.repository as sqlite_repo

        sqlite_repo.ensure_memory_schema()
        for item in sqlite_repo.search_memories_by_subject(
            actor_role="customer",
            subject_key=subject_key,
            query=query,
            limit=limit * 2,
        ):
            if item and (item.get("memory_type") or "") in ALLOWED_CUSTOMER_SALIENT_TYPES:
                items.append(item)
    except Exception as exc:
        logger.debug("customer durable recall sqlite failed: %s", type(exc).__name__)

    try:
        from services.memory.pg_repository import search_memories_by_subject_pg

        pg = search_memories_by_subject_pg(
            actor_role="customer",
            subject_key=subject_key,
            query=query,
            limit=limit * 2,
        )
        for item in pg.get("memories") or []:
            if item and (item.get("memory_type") or "") in ALLOWED_CUSTOMER_SALIENT_TYPES:
                items.append(item)
    except Exception:
        pass

    scored = [(score_memory_hit(i), i) for i in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    # Prefer customer_name at the front so prompt always sees known name.
    scored.sort(
        key=lambda pair: (
            0 if (pair[1].get("memory_type") or "") == "customer_name" else 1,
            -pair[0],
        )
    )
    out = []
    seen = set()
    for _, item in scored:
        key = (item.get("id"), (item.get("content") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "source": item.get("_memory_backend") or "customer_durable",
                "memory_id": item.get("id"),
                "memory_type": item.get("memory_type"),
                "content": item.get("content"),
                "confidence": 0.65,
            }
        )
        if len(out) >= limit:
            break
    return out


def propose_write(
    *,
    role: ActorRole,
    content: str,
    memory_type: str | None = None,
    source_message: str | None = None,
    subject_key: str = "owner",
) -> dict[str, Any]:
    """Owner: permanent preference/directive autosave (soft ACK). Customer: rejected (use auto_salient_write)."""
    if role != "owner":
        return {
            "ok": False,
            "blocked": True,
            "reason": "customer_must_use_auto_salient_write",
        }
    import services.memory.service as memory_service

    # Prefer explicit content path (Phase 4) over magic-phrase extraction.
    return memory_service.propose_permanent_memory_candidate(
        content=content,
        memory_type=memory_type,
        source_message=source_message or content,
        subject_key=subject_key or "owner",
    )


def confirm_write(*, role: ActorRole = "owner") -> dict[str, Any]:
    if role != "owner":
        return {"ok": False, "blocked": True, "reason": "owner_confirm_only"}
    import services.memory.service as memory_service

    return memory_service.confirm_pending_permanent_memory_candidate()


def auto_salient_write(
    *,
    phone: str,
    memory_type: str,
    content: str,
    source_message: str | None = None,
    salience: float = 2.0,
) -> dict[str, Any]:
    """1B customer auto-write â€” allowlisted types only, no owner confirm, no secrets."""
    if not feature_flags.customer_salient_memory_enabled():
        return {"ok": False, "skipped": True, "reason": "flag_off"}
    if not feature_flags.one_brain_foundation_enabled():
        return {"ok": False, "skipped": True, "reason": "one_brain_off"}

    mtype = (memory_type or "").strip().lower()
    if mtype not in ALLOWED_CUSTOMER_SALIENT_TYPES:
        return {"ok": False, "blocked": True, "reason": "type_not_allowlisted", "memory_type": mtype}

    text = (content or "").strip()
    if not text or len(text) < 2:
        return {"ok": False, "blocked": True, "reason": "empty_content"}

    # Block secret-looking content
    low = text.lower()
    if any(x in low for x in ("api_key", "password", ".env", "bearer ", "sk-")):
        return {"ok": False, "blocked": True, "reason": "secret_like_content"}

    classification = classify_memory_candidate(
        content=text,
        memory_type=mtype,
        source_message=source_message,
        owner_confirmed=True,  # customer salient is auto-confirmed within allowlist
        retention="permanent",
        sensitivity_level="normal",
        metadata={"actor_role": "customer", "salience": salience},
    )
    # Customer types are not in OWNER_CONFIRMATION_REQUIRED â€” classify may still block unknown.
    # Force allow for allowlisted customer types:
    if mtype in ALLOWED_CUSTOMER_SALIENT_TYPES:
        classification["should_save"] = True
        classification["owner_confirmation_required"] = False
        classification["owner_confirmed"] = True
        classification["blocked_reason"] = None

    if classification.get("blocked_reason") and mtype not in ALLOWED_CUSTOMER_SALIENT_TYPES:
        return {"ok": False, "blocked": True, "reason": classification.get("blocked_reason")}

    sk = subject_key_for("customer", phone)
    return _persist_actor_memory(
        memory_type=mtype,
        content=text,
        actor_role="customer",
        subject_key=sk,
        source="customer_salient_auto",
        salience=salience,
        owner_confirmed=True,
        metadata={"source_message": (source_message or "")[:200]},
    )


def _persist_actor_memory(
    *,
    memory_type: str,
    content: str,
    actor_role: str,
    subject_key: str,
    source: str,
    salience: float,
    owner_confirmed: bool,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = dict(metadata or {})
    meta.update(
        {
            "actor_role": actor_role,
            "subject_key": subject_key,
            "salience": salience,
        }
    )
    embedding_model = None
    embedding_vector = None
    try:
        from services.memory.embedding_provider import embed_text

        emb = embed_text(content)
        if (emb.get("status") == "success" or emb.get("success")) and emb.get("vector"):
            embedding_vector = emb["vector"]
            embedding_model = emb.get("model") or emb.get("embedding_model")
    except Exception:
        pass

    pg_ok = False
    memory_id = None
    try:
        from services.memory.pg_repository import create_memory_pg_idempotent

        dedupe = f"{actor_role}:{subject_key}:{memory_type}:{content[:80].lower()}"
        res = create_memory_pg_idempotent(
            write_dedupe_key=dedupe,
            memory_type=memory_type,
            content=content,
            owner_confirmed=owner_confirmed,
            importance=max(1, int(salience)),
            source=source,
            retention="permanent",
            sensitivity_level="normal",
            metadata=meta,
            embedding_model=embedding_model,
            embedding_vector=embedding_vector,
            actor_role=actor_role,
            subject_key=subject_key,
            salience=salience,
        )
        pg_ok = bool(res.get("success"))
        memory_id = (res.get("memory") or {}).get("id")
    except TypeError:
        # Older signature without actor fields â€” fall through to sqlite
        pass
    except Exception as exc:
        logger.debug("pg persist actor memory failed: %s", type(exc).__name__)

    try:
        import services.memory.repository as sqlite_repo

        sq = sqlite_repo.create_memory(
            memory_type=memory_type,
            content=content,
            owner_confirmed=owner_confirmed,
            importance=max(1, int(salience)),
            source=source,
            retention="permanent",
            sensitivity_level="normal",
            metadata=meta,
            actor_role=actor_role,
            subject_key=subject_key,
            salience=salience,
        )
        if not memory_id and isinstance(sq, dict):
            # create_memory returns the row dict (id at top level), not {"memory": ...}
            memory_id = sq.get("id") or (sq.get("memory") or {}).get("id")
    except Exception as exc:
        logger.warning("sqlite persist actor memory failed: %s", type(exc).__name__)
        if not pg_ok:
            return {"ok": False, "reason": "persist_failed"}

    return {
        "ok": True,
        "memory_id": memory_id,
        "actor_role": actor_role,
        "subject_key": subject_key,
        "memory_type": memory_type,
        "pg_ok": pg_ok,
    }


def mark_recalled(memory_ids: list[Any]) -> None:
    """Strengthen-on-use: bump last_recalled_at + recall_count (human pattern)."""
    ids = []
    for mid in memory_ids or []:
        try:
            ids.append(int(mid))
        except (TypeError, ValueError):
            continue
    if not ids:
        return
    try:
        import services.memory.repository as sqlite_repo

        sqlite_repo.bump_memory_recall(ids)
    except Exception:
        pass
    try:
        from services.memory.pg_repository import bump_memory_recall_pg

        bump_memory_recall_pg(ids)
    except Exception:
        pass


__all__ = [
    "ActorRole",
    "auto_salient_write",
    "confirm_write",
    "fade_factor",
    "mark_recalled",
    "propose_write",
    "recall",
    "score_memory_hit",
    "subject_key_for",
]

import os
import re
import sys
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import services.brain.manager_state as manager_state
import services.memory.repository as memory_repository
from services.brain.contracts import make_memory_context_packet, make_memory_write_decision_packet
from services.memory.contract import (
    ALLOWED_PERMANENT_MEMORY_TYPES,
    TEMPORARY_MEMORY_TYPES,
    classify_memory_candidate,
    make_memory_write_decision_from_candidate,
)
from services.memory.embedding_provider import PRIMARY_EMBEDDING_MODEL, embed_text
from services.memory.pg_repository import (
    create_memory_pg_idempotent,
    is_pgvector_available,
    is_postgres_available,
    log_memory_event_pg,
    search_memories_keyword_pg,
    search_memories_vector_pg,
    update_memory_metadata_pg,
)


PERMANENT_MEMORY_REQUEST_MARKERS = (
    "permanent memory me save",
    "permanent memory mein save",
    "permanent memory me daal",
    "permanent memory mein daal",
    "remember this permanently",
    "remember permanently",
    "permanently remember",
    "permanently yaad",
    "permanent yaad",
    "permanently yaad rakhna",
    "permanent memory",
    # Owner directive = already confirmed (no second haan) — soft auto-save.
    "yaad rakh",
    "yaad rakhna",
    "yaad rakho",
    "yaad rakh lo",
    "yaad rakhna hai",
    "hamesha yaad",
    "always remember",
    "aage se",
    "aise kiya karo",
    "aise karo",
    "aise hi karna",
    "aisi tarah",
    "is tarah karo",
    "isse pehle mat",
    "mat kiya karo",
)

MEMORY_REJECTION_PHRASES = {
    "no",
    "nahi",
    "nahin",
    "nhi",
    "cancel",
    "mat karo",
    "skip",
    "reject",
}

TEMPORARY_MEMORY_TERMS = (
    "diagnostic", "diagnostics", "cpu", "ram", "memory usage", "stream status",
    "status", "restart", "run karo", "command", "tool result", "draft", "script output",
)

CREATIVE_STYLE_REQUEST_TERMS = (
    "rj",
    "script",
    "intro",
    "content",
    "tone",
    "style",
    "bundeli",
    "hinglish",
    "comedy",
)

CREATIVE_REQUEST_ACTION_TERMS = (
    "banao",
    "likho",
    "draft",
    "generate",
    "intro",
    "script",
)


def _write_dedupe_key(content: str, memory_type: str) -> str:
    raw = f"{(memory_type or '').strip().lower()}|{(content or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _is_shadow_or_test_memory(item: dict) -> bool:
    try:
        if (item.get("source") or "") == "shadow_test":
            return True
        if (item.get("retention") or "") == "shadow_test":
            return True
        meta = item.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("shadow") is True:
            return True
        if isinstance(meta, dict) and str(meta.get("marker") or "").startswith("M2_A1_SHADOW_TEST"):
            return True
    except Exception:
        return False
    return False

SAVE_COMMAND_SUFFIX_PATTERNS = (
    r"^(?P<content>.+?)[\s,]*(?:is|iss|ye|yeh|this)\s+(?:baat|preference|fact|rule)?\s*ko\s+permanent memory\s+m(?:e|ein)\s+save\s+karo\s*$",
    r"^(?P<content>.+?)[\s,]*(?:is|iss|ye|yeh|this)\s+(?:baat|preference|fact|rule)?\s*ko\s+save\s+karo\s*$",
    r"^(?P<content>.+?)[\s,]*permanent memory\s+m(?:e|ein)\s+save\s+karo\s*$",
    r"^(?P<content>.+?)[\s,]*(?:ye|yeh|this)?\s*(?:preference|baat|fact|rule)?\s*permanently\s+yaad\s+rakhna\s*$",
    r"^(?P<content>.+?)[\s,]*remember this permanently\s*$",
    r"^(?P<content>.+?)[\s,]*remember permanently\s*$",
)

TRAILING_REFERENCE_PATTERN = re.compile(
    r"[\s,]*(?:is|iss|ye|yeh|this)\s+(?:baat|preference|fact|rule)(?:\s+ko)?$",
    re.IGNORECASE,
)

AMBIGUOUS_MEMORY_CANDIDATES = {
    "is baat ko",
    "iss baat ko",
    "ye baat",
    "yeh baat",
    "ye preference",
    "yeh preference",
    "this",
    "it",
}


def save_memory(memory_type: str, text: str, metadata: dict = None) -> dict:
    """
    Keeps existing short-term memory behavior intact.
    Non-correction permanent saves must use the explicit owner-confirmed flow.
    """
    if memory_type == "owner_correction" or "correction" in memory_type or "rule" in memory_type:
        manager_state.remember_owner_correction(text)
        return {
            "status": "short_term_saved",
            "memory_mode": "short_term_plus_permanent_text",
            "embedding_model_used": None,
            "memory_save_status": "short_term_saved",
        }

    return {
        "status": "blocked",
        "memory_mode": "short_term_plus_permanent_text",
        "embedding_model_used": None,
        "memory_save_status": "permanent_requires_explicit_owner_confirmation",
    }


def _search_short_term_memories(query: str, limit: int = 5) -> list[str]:
    # Hydrate Redis-backed corrections (ADR-008) — get_state() alone can miss them.
    corrections = manager_state.get_owner_corrections()
    hits = []
    query_lower = query.lower()
    for corr in corrections:
        if any(word in corr.lower() for word in query_lower.split() if len(word) > 2):
            hits.append(corr)
            if len(hits) >= limit:
                break
    return hits


def retrieve_active_permanent_memories(
    query: str,
    limit: int = 5,
    *,
    actor_role: str = "owner",
    subject_key: str = "owner",
) -> list[dict]:
    """
    Live read order (M2-A4):
    1) PostgreSQL pgvector semantic search if available
    2) PostgreSQL keyword search
    3) SQLite keyword fallback

    Always actor-scoped for owner (and any explicit subject).
    """
    q = (query or "").strip()
    if not q:
        return []
    role = (actor_role or "owner").strip().lower() or "owner"
    sk = (subject_key or "owner").strip() or "owner"

    fallback_reason_for_sqlite = None

    # 1) PG vector (semantic)
    try:
        if is_pgvector_available().get("available"):
            emb = embed_text(q)
            if emb.get("status") == "success":
                vec = emb.get("vector") or []
                if vec:
                    res = search_memories_vector_pg(
                        vec, top_k=limit, actor_role=role, subject_key=sk
                    )
                    hits = [h for h in (res.get("memories") or []) if h and not _is_shadow_or_test_memory(h)]
                    if hits:
                        for item in hits:
                            if item:
                                item["_memory_backend"] = "postgres_pgvector"
                                item["_embedding_model_used"] = PRIMARY_EMBEDDING_MODEL
                        return hits[:limit]
    except Exception:
        pass

    # 2) PG keyword
    try:
        if is_postgres_available().get("available"):
            res = search_memories_keyword_pg(
                q, limit=limit, actor_role=role, subject_key=sk
            )
            hits = [h for h in (res.get("memories") or []) if h and not _is_shadow_or_test_memory(h)]
            if hits:
                for item in hits:
                    if item:
                        item["_memory_backend"] = "postgres_keyword"
                        item["_embedding_model_used"] = None
                return hits[:limit]
    except Exception:
        pass

    # 3) SQLite fallback
    try:
        if not is_postgres_available().get("available"):
            fallback_reason_for_sqlite = "postgres_unavailable"
        elif not is_pgvector_available().get("available"):
            fallback_reason_for_sqlite = "pgvector_unavailable"
        else:
            fallback_reason_for_sqlite = "no_pg_hits"
    except Exception:
        fallback_reason_for_sqlite = "memory_backend_check_failed"

    try:
        hits = memory_repository.search_memories_keyword(
            q, limit=limit, actor_role=role, subject_key=sk
        )
        for item in hits:
            if item:
                item["_memory_backend"] = "sqlite_fallback"
                item["_embedding_model_used"] = None
                item["_memory_fallback_reason"] = fallback_reason_for_sqlite
        return hits
    except Exception:
        return []


def _is_creative_style_request(message: str) -> bool:
    msg_lower = (message or "").lower()
    if not msg_lower:
        return False
    has_style_subject = any(term in msg_lower for term in CREATIVE_STYLE_REQUEST_TERMS)
    has_create_action = any(term in msg_lower for term in CREATIVE_REQUEST_ACTION_TERMS)
    return has_style_subject and has_create_action


def _is_creative_style_memory(item: dict) -> bool:
    memory_type = (item.get("memory_type") or "").lower()
    content = (item.get("content") or "").lower()
    if memory_type != "owner_style_preference":
        return False
    return any(term in content for term in CREATIVE_STYLE_REQUEST_TERMS)


def _dedupe_memory_hits(items: list[dict], limit: int) -> list[dict]:
    seen = set()
    hits = []
    for item in items:
        content = (item.get("content") or "").strip().lower()
        key = content or item.get("id")
        if not key or key in seen:
            continue
        seen.add(key)
        hits.append(item)
        if len(hits) >= limit:
            break
    return hits


def _should_skip_permanent_context(query: str) -> bool:
    msg_lower = (query or "").lower()
    if _is_creative_style_request(msg_lower):
        return False
    words = set(re.findall(r"[a-z0-9]+", msg_lower))
    try:
        import services.brain.feature_flags as feature_flags

        if feature_flags.one_brain_foundation_enabled():
            # Keep style/ops prefs injectable; only skip hard ephemeral ops noise.
            hard = {"diagnostic", "diagnostics", "cpu", "ram", "restart"}
            return bool(words & hard) or "memory usage" in msg_lower or "stream status" in msg_lower
    except Exception:
        pass
    return any((t in msg_lower if " " in t else t in words) for t in TEMPORARY_MEMORY_TERMS)


def _retrieve_creative_memory_lightweight(query: str, limit: int = 3) -> list[dict]:
    """Fast keyword-only memory for creative hot path (skip pgvector/postgres probes)."""
    import services.memory.repository as memory_repository

    hits: list[dict] = []
    try:
        for item in memory_repository.search_memories_keyword(query, limit=limit):
            if item:
                item["_memory_backend"] = "sqlite_keyword_fast"
                item["_memory_fallback_reason"] = "creative_fast_path"
                hits.append(item)
    except Exception:
        pass
    if len(hits) >= limit or not _is_creative_style_request(query):
        return _dedupe_memory_hits(hits, limit)
    try:
        style_preferences = memory_repository.list_active_memories(
            limit=50,
            memory_type="owner_style_preference",
        )
    except Exception:
        style_preferences = []
    for item in style_preferences:
        if _is_creative_style_memory(item):
            item["_memory_backend"] = "sqlite_style_preference"
            hits.append(item)
        if len(hits) >= limit:
            break
    return _dedupe_memory_hits(hits, limit)


def retrieve_contextual_permanent_memories(query: str, limit: int = 3) -> list[dict]:
    """
    Retrieves permanent memories for prompt injection.
    One-brain mode: creative path also uses pgvector (not SQLite-only shortcut).
    """
    try:
        import services.brain.feature_flags as feature_flags

        one_brain = feature_flags.one_brain_foundation_enabled()
    except Exception:
        one_brain = False

    if _is_creative_style_request(query) and not one_brain:
        return _retrieve_creative_memory_lightweight(query, limit=limit)

    if _should_skip_permanent_context(query):
        return []

    hits = retrieve_active_permanent_memories(query, limit=limit)
    if len(hits) >= limit or not _is_creative_style_request(query):
        return _dedupe_memory_hits(hits, limit)

    try:
        style_preferences = memory_repository.list_active_memories(
            limit=50,
            memory_type="owner_style_preference",
        )
    except Exception:
        style_preferences = []

    for item in style_preferences:
        if _is_creative_style_memory(item):
            item["match_type"] = "contextual_keyword"
            hits.append(item)

    return _dedupe_memory_hits(hits, limit)


def search_memories(query: str, limit: int = 5) -> list:
    """
    Searches short-term corrections first, then permanent keyword memories.
    Returns simple text hits for backward compatibility with existing trace code.
    """
    hits = list(_search_short_term_memories(query, limit=limit))
    remaining = max(limit - len(hits), 0)
    if remaining:
        for item in retrieve_contextual_permanent_memories(query, limit=remaining):
            content = item.get("content")
            if content:
                hits.append(content)
    return hits


def is_explicit_permanent_memory_request(message: str) -> bool:
    """Deprecated router — always False. propose_permanent_memory is interpreter→catalog."""
    del message
    return False


def is_memory_rejection_message(message: str) -> bool:
    cleaned = (message or "").lower().strip().strip(".!,?").strip()
    return cleaned in MEMORY_REJECTION_PHRASES


def _extract_permanent_memory_content(owner_message: str) -> str:
    text = (owner_message or "").strip()
    if not text:
        return ""

    def clean_candidate(value: str) -> str:
        candidate = (value or "").strip(" \t\r\n,.:;-\"'")
        candidate = TRAILING_REFERENCE_PATTERN.sub("", candidate).strip(" \t\r\n,.:;-\"'")
        if candidate.lower() in AMBIGUOUS_MEMORY_CANDIDATES:
            return ""
        return candidate

    for pattern in SAVE_COMMAND_SUFFIX_PATTERNS:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_candidate(match.group("content"))

    lower = text.lower()
    for marker in PERMANENT_MEMORY_REQUEST_MARKERS:
        idx = lower.find(marker)
        if idx == -1:
            continue
        before = clean_candidate(text[:idx])
        after = clean_candidate(text[idx + len(marker):])
        if before:
            return before
        if after:
            return after
    return ""


def _infer_memory_type(content: str) -> str:
    lower = (content or "").lower()
    words = set(re.findall(r"[a-z0-9]+", lower))  # whole-word match: "vikram" is not "ram"
    def has(term: str) -> bool:
        return term in lower if " " in term else term in words
    if any(has(t) for t in TEMPORARY_MEMORY_TERMS):
        if has("cpu") or has("ram") or "diagnostic" in lower:
            return "diagnostic_result"
        if has("draft") or "script output" in lower:
            return "draft_content"
        return "temporary_command"
    try:
        from services.memory.future_intention import is_future_intention_statement

        if is_future_intention_statement(content):
            return "neena_future_intention"
    except Exception:
        pass
    if any(
        t in lower
        for t in (
            "karna hai",
            "plan hai",
            "intention",
            "kal ",
            "parso ",
            "todo",
        )
    ) and any(t in lower for t in ("karna", "plan", "intention", "todo")):
        return "neena_future_intention"
    if any(has(t) for t in ("tone", "style", "preference", "rakha karo", "rakhna", "bundeli", "hinglish", "comedy")):
        return "owner_style_preference"
    if any(has(t) for t in ("station", "brand", "identity", "orai radio")):
        return "station_identity"
    if any(has(t) for t in ("rule", "policy", "always", "never", "kabhi", "mat")):
        return "station_policy"
    return "operational_preference"


def get_pending_permanent_memory_candidate() -> dict | None:
    pending = manager_state.get_pending_action()
    if not pending or pending.get("action_type") != "permanent_memory_save":
        return None
    payload = pending.get("payload") or {}
    return payload.get("memory_candidate")


def is_direct_memory_question(message: str) -> bool:
    """Deprecated router — always False. Memory asks go via interpreter→catalog tools."""
    del message
    return False


def build_local_memory_recall_packet(
    message: str,
    limit: int = 3,
    mem_packet: dict | None = None,
) -> dict | None:
    """Facts for PERMANENT_MEMORY_RETRIEVAL — no canned Sir Hinglish."""
    items: list[dict] = []
    seen: set[str] = set()
    source = "permanent"

    if mem_packet and mem_packet.get("hits"):
        for hit in mem_packet.get("hits") or []:
            if (hit or {}).get("source") == "short_term":
                continue
            content = (hit.get("content") or "").strip()
            if content and content not in seen:
                seen.add(content)
                items.append(
                    {
                        "content": content,
                        "memory_type": hit.get("memory_type"),
                        "source": hit.get("source") or "permanent",
                    }
                )
            if len(items) >= limit:
                break

    if not items:
        hits = retrieve_active_permanent_memories(message, limit=limit)
        for item in hits:
            content = (item.get("content") or "").strip()
            if content and content not in seen:
                seen.add(content)
                items.append(
                    {
                        "content": content,
                        "memory_type": item.get("memory_type"),
                        "source": "permanent",
                    }
                )
            if len(items) >= limit:
                break

    if not items:
        corr = [c.strip() for c in manager_state.get_owner_corrections()[-limit:] if c.strip()]
        if not corr:
            return None
        source = "short_term_corrections"
        items = [{"content": c, "memory_type": "owner_correction", "source": source} for c in corr]

    backend = None
    if mem_packet:
        backend = mem_packet.get("memory_backend")
    contents = [i["content"] for i in items]
    packet = {
        "tool": "permanent_memory_retrieval",
        "status": "ok",
        "count": len(items),
        "source": source,
        "memory_backend": backend,
        "memories": items,
    }
    lines = [f"{idx}. [{it.get('memory_type') or '-'}] {it['content']}" for idx, it in enumerate(items, 1)]
    fallback = f"Permanent memory recall. count={len(items)} source={source}.\n" + "\n".join(lines)
    return {
        "factual_packet": packet,
        "fallback_line": fallback,
        "action_type": "PERMANENT_MEMORY_RETRIEVAL",
        # BC for older callers that expect text:
        "contents": contents,
    }


def format_local_memory_answer(
    message: str,
    limit: int = 3,
    mem_packet: dict | None = None,
) -> str | None:
    """Backward-compatible text wrapper — prefers factual packet fallback_line."""
    out = build_local_memory_recall_packet(message, limit=limit, mem_packet=mem_packet)
    if not out:
        return None
    return out.get("fallback_line")

def _factual_memory_save_fallback(decision: dict, *, status: str, postgres_memory_id, sqlite_memory_id, postgres_write_status: str, sqlite_mirror_status: str) -> str:
    """Short factual line only — owner Hinglish via maybe_humanize_report + factual_packet."""
    content = (decision.get("content") or "").strip()
    snippet = content if len(content) <= 120 else content[:117] + "..."
    mtype = decision.get("memory_type") or "operational_preference"
    if status == "saved":
        return (
            f"Permanent memory saved. type={mtype} content={snippet} "
            f"postgres_id={postgres_memory_id} sqlite_id={sqlite_memory_id}."
        )
    return (
        f"Permanent memory save failed. type={mtype} "
        f"postgres={postgres_write_status} sqlite={sqlite_mirror_status}."
    )


def _persist_confirmed_permanent_candidate(
    confirmed_candidate: dict,
    owner_message: str | None = None,
    *,
    soft_ack: bool = True,
    event_type: str = "created_from_owner_directive",
) -> dict:
    """Write an already-confirmed permanent candidate (Postgres primary + SQLite mirror).

    Returns factual reply + factual_packet. Do not put polished owner Hinglish here.
    """
    decision = make_memory_write_decision_from_candidate(confirmed_candidate)
    if not decision.get("should_save"):
        manager_state.clear_pending_action()
        blocked = decision.get("blocked_reason") or "blocked"
        packet = {
            "tool": "permanent_memory_save",
            "status": "blocked",
            "saved": False,
            "blocked_reason": blocked,
            "content": decision.get("content"),
            "memory_type": decision.get("memory_type"),
        }
        return {
            "status": "blocked",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "permanent_memory_blocked",
            "candidate": confirmed_candidate,
            "decision": decision,
            "factual_packet": packet,
            "reply": f"Permanent memory blocked: {blocked}.",
        }

    write_dedupe_key = _write_dedupe_key(decision["content"], decision["memory_type"])
    memory_write_backend = "failed"
    postgres_write_status = "not_attempted"
    postgres_embedding_status = "not_attempted"
    postgres_memory_id = None
    sqlite_mirror_status = "not_attempted"
    sqlite_memory_id = None
    sqlite_saved = None
    pg_failure_reason = None

    try:
        if is_postgres_available().get("available"):
            postgres_write_status = "attempted"
            embedding_vec = None
            embedding_model = None
            emb = embed_text(decision["content"])
            if emb.get("status") == "success":
                vec = emb.get("vector") or []
                if len(vec) == 3072:
                    embedding_vec = vec
                    embedding_model = PRIMARY_EMBEDDING_MODEL
                    postgres_embedding_status = "embedded"
                else:
                    postgres_embedding_status = f"dim_mismatch_{len(vec)}"
            else:
                postgres_embedding_status = emb.get("status") or "embed_failed"

            pg_saved = create_memory_pg_idempotent(
                write_dedupe_key=write_dedupe_key,
                memory_type=decision["memory_type"],
                content=decision["content"],
                owner_confirmed=True,
                importance=1,
                source="owner_message",
                retention=decision["retention"],
                sensitivity_level=decision["sensitivity_level"],
                expires_at=decision.get("expires_at"),
                metadata={
                    "source_message": decision.get("source_message"),
                    "reason": decision.get("reason"),
                    "stage": "owner_directive_autosave",
                    "write_backend": "postgres_primary",
                    "embedding_model": embedding_model or PRIMARY_EMBEDDING_MODEL,
                },
                embedding_model=embedding_model,
                embedding_vector=embedding_vec,
            )
            if pg_saved.get("success"):
                postgres_memory_id = (pg_saved.get("memory") or {}).get("id")
                postgres_write_status = "deduped_existing" if pg_saved.get("deduped") else "success"
                memory_write_backend = "postgres_primary"
                log_memory_event_pg(
                    memory_id=postgres_memory_id,
                    event_type=event_type,
                    user_message=owner_message or decision.get("source_message"),
                    assistant_response="Permanent memory saved to PostgreSQL (primary).",
                    metadata={"stage": "owner_directive_autosave", "write_backend": "postgres_primary"},
                )
            else:
                pg_failure_reason = pg_saved.get("error_type") or pg_saved.get("reason")
                postgres_write_status = f"failed:{pg_failure_reason}"
        else:
            pg_failure_reason = "postgres_unavailable"
            postgres_write_status = "failed:postgres_unavailable"
    except Exception as exc:
        pg_failure_reason = type(exc).__name__
        postgres_write_status = f"failed:{pg_failure_reason}"

    try:
        sqlite_mirror_status = "attempted"
        existing_sqlite = memory_repository.find_confirmed_memory_by_content(decision["content"])
        if existing_sqlite:
            sqlite_saved = existing_sqlite
            sqlite_mirror_status = "deduped_existing"
        else:
            sqlite_metadata = {
                "source_message": decision.get("source_message"),
                "reason": decision.get("reason"),
                "stage": "owner_directive_autosave",
                "write_dedupe_key": write_dedupe_key,
            }
            if postgres_memory_id:
                sqlite_metadata["write_backend"] = "sqlite_mirror"
                sqlite_metadata["postgres_memory_id"] = postgres_memory_id
            else:
                sqlite_metadata["write_backend"] = "sqlite_fallback"
                if pg_failure_reason:
                    sqlite_metadata["postgres_write_failure"] = pg_failure_reason

            sqlite_saved = memory_repository.create_memory(
                memory_type=decision["memory_type"],
                content=decision["content"],
                owner_confirmed=True,
                importance=1,
                source="owner_message",
                retention=decision["retention"],
                sensitivity_level=decision["sensitivity_level"],
                expires_at=decision.get("expires_at"),
                metadata=sqlite_metadata,
            )
            memory_repository.log_memory_event(
                memory_id=sqlite_saved["id"],
                event_type=event_type,
                user_message=owner_message or decision.get("source_message"),
                assistant_response=(
                    "Permanent memory mirrored to SQLite."
                    if postgres_memory_id
                    else "Permanent memory saved to SQLite fallback."
                ),
                metadata={"stage": "owner_directive_autosave"},
            )
            sqlite_mirror_status = "success"

        sqlite_memory_id = sqlite_saved.get("id")
        if postgres_memory_id and sqlite_memory_id:
            update_memory_metadata_pg(
                postgres_memory_id,
                {"sqlite_mirror_id": sqlite_memory_id},
            )
    except Exception as exc:
        sqlite_mirror_status = f"failed:{type(exc).__name__}"

    manager_state.clear_pending_action()

    if postgres_memory_id and sqlite_memory_id:
        memory_save_status = "permanent_saved_postgres_primary_sqlite_mirror"
        memory_write_backend = "postgres_primary"
        status = "saved"
    elif postgres_memory_id:
        memory_save_status = "permanent_saved_postgres_primary_sqlite_mirror_failed"
        memory_write_backend = "postgres_primary"
        status = "saved"
    elif sqlite_memory_id:
        memory_save_status = "permanent_saved_sqlite_fallback"
        memory_write_backend = "sqlite_fallback"
        status = "saved"
    else:
        memory_save_status = "permanent_save_failed"
        memory_write_backend = "failed"
        status = "failed"

    if status == "saved":
        reply = _factual_memory_save_fallback(
            decision,
            status=status,
            postgres_memory_id=postgres_memory_id,
            sqlite_memory_id=sqlite_memory_id,
            postgres_write_status=postgres_write_status,
            sqlite_mirror_status=sqlite_mirror_status,
        )
    else:
        reply = _factual_memory_save_fallback(
            decision,
            status=status,
            postgres_memory_id=postgres_memory_id,
            sqlite_memory_id=sqlite_memory_id,
            postgres_write_status=postgres_write_status,
            sqlite_mirror_status=sqlite_mirror_status,
        )

    packet = {
        "tool": "permanent_memory_save",
        "status": status,
        "saved": status == "saved",
        "autosave": True,
        "owner_confirmed": True,
        "content": decision.get("content"),
        "memory_type": decision.get("memory_type"),
        "postgres_memory_id": postgres_memory_id,
        "sqlite_memory_id": sqlite_memory_id,
        "memory_write_backend": memory_write_backend,
        "postgres_write_status": postgres_write_status,
        "sqlite_mirror_status": sqlite_mirror_status,
        "intent_hint": "acknowledge_saved_preference" if status == "saved" else "report_save_failure",
    }

    return {
        "status": status,
        "ok": status == "saved",
        "require_confirmation": False,
        "memory_save_status": memory_save_status,
        "memory_write_backend": memory_write_backend,
        "postgres_write_status": postgres_write_status,
        "postgres_embedding_status": postgres_embedding_status,
        "postgres_memory_id": postgres_memory_id,
        "sqlite_mirror_status": sqlite_mirror_status,
        "sqlite_memory_id": sqlite_memory_id,
        "pg_failure_reason": pg_failure_reason,
        "candidate": confirmed_candidate,
        "decision": decision,
        "memory": sqlite_saved if sqlite_memory_id else None,
        "factual_packet": packet,
        "reply": reply,
        "action_type": "PERMANENT_MEMORY_SAVED",
    }


def create_pending_permanent_memory_candidate(owner_message: str) -> dict:
    """Owner explicit remember/directive — save immediately (no second haan)."""
    content = _extract_permanent_memory_content(owner_message)
    if not content:
        decision = make_memory_write_decision_packet(
            should_save=False,
            memory_type=None,
            content=None,
            reason="Exact memory content was not provided.",
            owner_confirmation_required=False,
            owner_confirmed=False,
            retention="blocked",
            sensitivity_level="normal",
            source_message=owner_message,
            blocked_reason="memory_content_missing",
        )
        return {
            "status": "needs_content",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "permanent_memory_needs_content",
            "decision": decision,
            "factual_packet": {
                "tool": "permanent_memory_save",
                "status": "needs_content",
                "saved": False,
            },
            "reply": "Permanent memory needs exact content (one clear line).",
        }

    memory_type = _infer_memory_type(content)
    if memory_type in TEMPORARY_MEMORY_TYPES:
        memory_type = "operational_preference"
    candidate = classify_memory_candidate(
        content=content,
        memory_type=memory_type,
        source_message=owner_message,
        owner_confirmed=True,
        retention="permanent",
        sensitivity_level="normal",
        metadata={"stage": "owner_directive_autosave", "embedding": "disabled"},
    )
    decision = make_memory_write_decision_from_candidate(candidate)

    if candidate.get("blocked_reason") and candidate.get("blocked_reason") != "owner_confirmation_required":
        return {
            "status": "blocked",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "permanent_memory_blocked",
            "candidate": candidate,
            "decision": decision,
            "reply": f"Permanent memory blocked: {candidate.get('reason')}",
        }

    return _persist_confirmed_permanent_candidate(
        candidate,
        owner_message,
        soft_ack=True,
        event_type="created_from_owner_directive",
    )


def propose_permanent_memory_candidate(
    *,
    content: str,
    memory_type: str | None = None,
    source_message: str | None = None,
    subject_key: str = "owner",
) -> dict:
    """Owner preference/rule from interpreter — save immediately (no second haan)."""
    text = (content or "").strip()
    if not text:
        return {
            "status": "needs_content",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "permanent_memory_needs_content",
            "reply": "Permanent memory content missing. Provide one clear line to save.",
        }
    mtype = (memory_type or _infer_memory_type(text)).strip().lower()
    if mtype in TEMPORARY_MEMORY_TYPES:
        mtype = "operational_preference"
    if mtype not in ALLOWED_PERMANENT_MEMORY_TYPES:
        mtype = "operational_preference"
    candidate = classify_memory_candidate(
        content=text,
        memory_type=mtype,
        source_message=source_message or text,
        owner_confirmed=True,
        retention="permanent",
        sensitivity_level="normal",
        metadata={
            "stage": "owner_directive_autosave",
            "actor_role": "owner",
            "subject_key": subject_key or "owner",
        },
    )
    decision = make_memory_write_decision_from_candidate(candidate)
    if candidate.get("blocked_reason") and candidate.get("blocked_reason") != "owner_confirmation_required":
        return {
            "status": "blocked",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "permanent_memory_blocked",
            "candidate": candidate,
            "decision": decision,
            "reply": f"Cannot save permanently: {candidate.get('reason')}",
        }
    out = _persist_confirmed_permanent_candidate(
        candidate,
        source_message or text,
        soft_ack=True,
        event_type="created_from_owner_directive",
    )
    out["action_type"] = "PROPOSE_PERMANENT_MEMORY"
    return out


def confirm_pending_permanent_memory_candidate(owner_message: str | None = None) -> dict:
    """Legacy: flush any leftover pending candidate (new path autosaves)."""
    pending = manager_state.get_pending_action()
    candidate = get_pending_permanent_memory_candidate()
    if not pending or not candidate:
        return {
            "status": "no_pending_candidate",
            "ok": False,
            "require_confirmation": False,
            "memory_save_status": "no_pending_permanent_memory_candidate",
            "reply": "No pending permanent memory candidate. Provide the exact line to save.",
        }

    confirmed_candidate = classify_memory_candidate(
        content=candidate.get("content", ""),
        memory_type=candidate.get("memory_type"),
        source_message=candidate.get("source_message"),
        owner_confirmed=True,
        retention=candidate.get("retention", "permanent"),
        sensitivity_level=candidate.get("sensitivity_level", "normal"),
        expires_at=candidate.get("expires_at"),
        metadata=candidate.get("metadata") or {},
    )
    return _persist_confirmed_permanent_candidate(
        confirmed_candidate,
        owner_message,
        soft_ack=True,
        event_type="created_from_owner_confirmation",
    )

def cancel_pending_permanent_memory_candidate() -> dict:
    if get_pending_permanent_memory_candidate():
        manager_state.clear_pending_action()
        packet = {
            "tool": "permanent_memory_cancel",
            "status": "cancelled",
            "saved": False,
            "applied": True,
        }
        fallback = "Permanent memory candidate cancelled. Nothing saved."
        return {
            "status": "cancelled",
            "memory_save_status": "permanent_memory_cancelled",
            "factual_packet": packet,
            "reply": fallback,
        }
    packet = {
        "tool": "permanent_memory_cancel",
        "status": "no_pending_candidate",
        "saved": False,
        "applied": False,
    }
    fallback = "No pending permanent memory candidate."
    return {
        "status": "no_pending_candidate",
        "memory_save_status": "no_pending_permanent_memory_candidate",
        "factual_packet": packet,
        "reply": fallback,
    }

def build_memory_context(owner_message: str) -> str:
    """
    Builds a compact memory context block using short-term state first, then
    permanent keyword memories when available. No embeddings are used in M1-B1.
    """
    state_context = manager_state.build_short_context()
    short_hits = _search_short_term_memories(owner_message)
    permanent_hits = retrieve_contextual_permanent_memories(owner_message, limit=3)

    lines = [state_context]
    if short_hits:
        lines.append("\nRELEVANT SHORT-TERM RULES/CORRECTIONS:")
        for idx, hit in enumerate(short_hits, 1):
            lines.append(f"- Hit {idx}: {hit}")

    if permanent_hits:
        lines.append("\nRELEVANT PERMANENT MEMORIES:")
        for idx, item in enumerate(permanent_hits, 1):
            lines.append(
                f"- Hit {idx}: [{item.get('memory_type')}] {item.get('content')}"
            )

    lines.append("\nMEMORY SYSTEM INFORMATION:")
    lines.append("- Mode: short_term_plus_permanent_text")
    lines.append("- Permanent memory: PostgreSQL read-first (pgvector -> keyword) with SQLite keyword fallback.")
    lines.append(f"- Embeddings: enabled for retrieval via {PRIMARY_EMBEDDING_MODEL} when pgvector is available.")

    return "\n".join(lines)


def get_memory_context_packet(owner_message: str) -> dict:
    if _should_skip_permanent_context(owner_message):
        short_hits = _search_short_term_memories(owner_message)
        hits = [{"source": "short_term", "content": item} for item in short_hits]
        packet = make_memory_context_packet(
            memory_mode="short_term_only",
            short_context_used=True,
            memory_search_used="short_term_only",
            memory_hits_count=len(hits),
            hits=hits,
            context_text=build_memory_context(owner_message),
            source="manager_state_only",
            confidence=0.3 if hits else 0.1,
            expires_at=None,
            retrieval_status="ok",
        )
        packet["memory_backend"] = None
        packet["semantic_memory_used"] = False
        packet["embedding_model_used"] = None
        packet["memory_fallback_reason"] = "skipped_temporary_request"
        return packet

    permanent_hits = retrieve_contextual_permanent_memories(owner_message, limit=3)
    short_hits = _search_short_term_memories(owner_message)
    hits = [{"source": "short_term", "content": item} for item in short_hits]
    memory_backend = None
    semantic_used = False
    embedding_model_used = None

    for item in permanent_hits:
        backend = item.get("_memory_backend") or "permanent_unknown"
        memory_backend = memory_backend or backend
        if backend == "postgres_pgvector":
            semantic_used = True
            embedding_model_used = item.get("_embedding_model_used") or PRIMARY_EMBEDDING_MODEL
        hits.append(
            {
                "source": backend,
                "memory_id": item.get("id"),
                "memory_type": item.get("memory_type"),
                "content": item.get("content"),
                "confidence": 0.7 if backend == "postgres_pgvector" else 0.6,
            }
        )

    fallback_reason = None
    if not permanent_hits:
        try:
            if not is_postgres_available().get("available"):
                fallback_reason = "postgres_unavailable"
            elif not is_pgvector_available().get("available"):
                fallback_reason = "pgvector_unavailable"
            else:
                fallback_reason = "no_hits"
        except Exception:
            fallback_reason = "memory_backend_check_failed"
    else:
        # If we ended up in SQLite fallback, carry reason through for trace clarity.
        if (memory_backend or "").startswith("sqlite"):
            fallback_reason = permanent_hits[0].get("_memory_fallback_reason")

    packet = make_memory_context_packet(
        memory_mode="short_term_plus_permanent_text",
        short_context_used=True,
        memory_search_used="short_term_then_pgvector_then_pg_keyword_then_sqlite",
        memory_hits_count=len(hits),
        hits=hits,
        context_text=build_memory_context(owner_message),
        source="manager_state_pg_then_sqlite",
        confidence=0.7 if semantic_used else (0.6 if permanent_hits else 0.3),
        expires_at=None,
        retrieval_status="ok",
    )
    # Extra fields (used for trace only; safe to ignore by callers).
    packet["memory_backend"] = memory_backend
    packet["semantic_memory_used"] = semantic_used
    packet["embedding_model_used"] = embedding_model_used
    packet["memory_fallback_reason"] = fallback_reason
    return packet


def get_memory_status() -> dict:
    return {
        "memory_mode": "short_term_plus_permanent_text",
        "embedding_model_used": PRIMARY_EMBEDDING_MODEL,
        "memory_search_used": "short_term_then_pgvector_then_pg_keyword_then_sqlite",
        "memory_hits_count": 0,
        "memory_save_status": "not_attempted",
        "permanent_memory": "enabled_pg_read_with_sqlite_fallback",
    }

"""Owner-commanded memory correction: list / update / delete (soft), confirmation-gated.

The owner is the final authority over permanent memory. This service lets Neena
show saved memories, then update or soft-delete one ONLY after explicit owner
confirmation. Delete is a soft-expire (kept for audit), update refreshes the
embedding so semantic recall stays correct. Never claims success it did not do.

List identity is stable Postgres ``id`` (not volatile 1..N rank).
Replies are factual_packet + short English fallback — humanize elsewhere.
"""
from __future__ import annotations

import re

import services.brain.manager_state as manager_state
from services.memory.pg_repository import (
    expire_memory_pg,
    get_memory_pg,
    list_active_memories_pg,
    log_memory_event_pg,
    search_memories_keyword_pg,
    update_memory_content_pg,
    update_memory_embedding_pg,
)

_PENDING_ACTION_TYPE = "memory_edit"
_EMBEDDING_DIM = 3072
_ID_IN_TEXT = re.compile(r"\bid\s*[:=]?\s*(\d+)\b", re.IGNORECASE)

# Soft narrative / calendar types — shown first in list for edit UX.
_NARRATIVE_TYPES = (
    "neena_self_identity",
    "neena_personality_profile",
    "neena_life_episode",
    "neena_mind_architecture",
    "neena_day_summary",
    "neena_week_summary",
    "neena_future_intention",
)


def _active(limit: int = 100) -> list[dict]:
    mems = list_active_memories_pg(limit=limit).get("memories") or []
    return sorted(mems, key=lambda m: int(m.get("id") or 0))


def _is_active_row(mem: dict | None) -> bool:
    if not mem:
        return False
    if mem.get("owner_confirmed") is False:
        return False
    if (mem.get("retention") or "").lower() == "blocked":
        return False
    return True


def _clip(text: str, n: int = 160) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= n:
        return t
    return t[: n - 3] + "..."


def build_owner_memories_list_packet(limit: int = 20) -> dict:
    mems = _active(limit)
    items = []
    for mem in mems:
        mtype = mem.get("memory_type") or "note"
        meta = mem.get("metadata") if isinstance(mem.get("metadata"), dict) else {}
        items.append(
            {
                "id": mem.get("id"),
                "memory_type": mtype,
                "section": meta.get("section") or (
                    "narrative" if mtype in _NARRATIVE_TYPES else "preference"
                ),
                "content": _clip(mem.get("content") or "", 200),
                "target_date_ist": meta.get("target_date_ist"),
                "date_ist": meta.get("date_ist"),
            }
        )
    # Narrative / future / day first for edit UX, then preferences by id.
    items.sort(
        key=lambda it: (
            0 if (it.get("memory_type") or "") in _NARRATIVE_TYPES else 1,
            int(it.get("id") or 0),
        )
    )
    packet = {
        "tool": "manage_memory",
        "operation": "list",
        "status": "ok",
        "count": len(items),
        "memories": items,
        "hint": "Edit/delete with stable id (id=<n>).",
    }
    if not items:
        fallback = "Owner permanent memories count=0."
    else:
        lines = [
            f"id={it.get('id')} [{it.get('memory_type')}] {it.get('content')}"
            for it in items
        ]
        fallback = (
            f"Owner permanent memories count={len(items)} (stable id for edit/delete).\n"
            + "\n".join(lines)
        )
    return {
        "status": "listed",
        "factual_packet": packet,
        "fallback_line": fallback,
        "reply": fallback,
        "action_type": "MANAGE_MEMORY",
    }


def list_owner_memories_text(limit: int = 20) -> str:
    return build_owner_memories_list_packet(limit=limit)["fallback_line"]


def _resolve_target(target) -> dict | None:
    """Resolve by stable Postgres id first; then keyword search. No volatile rank index."""
    s = str(target if target is not None else "").strip()
    if not s:
        return None

    mid: int | None = None
    m = _ID_IN_TEXT.search(s)
    if m:
        mid = int(m.group(1))
    elif s.isdigit():
        mid = int(s)
    else:
        digits = re.findall(r"\d+", s)
        if len(digits) == 1 and any(
            k in s.lower() for k in ("id", "memory", "no", "number", "#")
        ):
            mid = int(digits[0])

    if mid is not None:
        found = get_memory_pg(mid).get("memory")
        if found and _is_active_row(found):
            return found

    found = search_memories_keyword_pg(
        s, limit=1, actor_role="owner", subject_key="owner"
    ).get("memories") or []
    return found[0] if found else None


def create_pending_memory_edit(operation: str, target=None, new_content: str | None = None) -> dict:
    """Prepare a memory list/update/delete. Update/delete need owner confirmation."""
    operation = (operation or "").strip().lower()
    if operation in ("list", "show", ""):
        return build_owner_memories_list_packet()
    if operation not in ("update", "delete"):
        packet = {
            "tool": "manage_memory",
            "operation": operation or None,
            "status": "clarify",
            "hint": "Use list, update, or delete.",
        }
        fallback = "Manage memory needs operation=list|update|delete."
        return {
            "status": "clarify",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MANAGE_MEMORY",
        }

    mem = _resolve_target(target)
    if not mem:
        packet = {
            "tool": "manage_memory",
            "operation": operation,
            "status": "not_found",
            "hint": "Pass stable id (id=<n>) or list memories first.",
        }
        fallback = "Manage memory target not found. Provide stable id or list first."
        return {
            "status": "not_found",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MANAGE_MEMORY",
        }
    if operation == "update" and not (new_content or "").strip():
        packet = {
            "tool": "manage_memory",
            "operation": "update",
            "status": "needs_content",
            "memory_id": mem.get("id"),
            "old_content": _clip(mem.get("content") or "", 140),
        }
        fallback = f"Manage memory update needs new_content for id={mem.get('id')}."
        return {
            "status": "needs_content",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MANAGE_MEMORY",
        }

    manager_state.set_pending_action(
        action_type=_PENDING_ACTION_TYPE,
        category="memory",
        risk_level="medium",
        protected=False,
        executable_now=True,
        requires_stage="owner_confirmation",
        status="pending_owner_confirmation",
        expires_after_turns=3,
        payload={
            "operation": operation,
            "memory_id": mem.get("id"),
            "old_content": mem.get("content"),
            "new_content": new_content,
            "memory_type": mem.get("memory_type"),
        },
    )
    old = _clip(mem.get("content") or "", 140)
    mid = mem.get("id")
    packet = {
        "tool": "manage_memory",
        "operation": operation,
        "status": "pending_confirmation",
        "memory_id": mid,
        "memory_type": mem.get("memory_type"),
        "old_content": old,
        "new_content": _clip(new_content or "", 140) if operation == "update" else None,
        "require_confirmation": True,
    }
    if operation == "delete":
        fallback = (
            f"Manage memory pending delete. id={mid} old={old}. Confirm haan/nahi."
        )
    else:
        fallback = (
            f"Manage memory pending update. id={mid} old={old} "
            f"new={_clip(new_content or '', 140)}. Confirm haan/nahi."
        )
    return {
        "status": "pending_confirmation",
        "factual_packet": packet,
        "fallback_line": fallback,
        "reply": fallback,
        "require_confirmation": True,
        "action_type": "MANAGE_MEMORY",
    }


def get_pending_memory_edit() -> dict | None:
    pending = manager_state.get_pending_action()
    # Prefer memory slot even when live_ops has higher global priority.
    try:
        slots = (manager_state.get_state() or {}).get("pending_slots") or {}
        mem = slots.get("memory")
        if isinstance(mem, dict) and (mem.get("action_type") or "") == _PENDING_ACTION_TYPE:
            return mem.get("payload") or {}
    except Exception:
        pass
    if not pending or pending.get("action_type") != _PENDING_ACTION_TYPE:
        return None
    return pending.get("payload") or {}


def cancel_pending_memory_edit() -> dict:
    manager_state.clear_pending_action(slot="memory")
    packet = {
        "tool": "manage_memory",
        "operation": "cancel",
        "status": "cancelled",
        "applied": False,
    }
    fallback = "Manage memory change cancelled. No write applied."
    return {
        "status": "cancelled",
        "factual_packet": packet,
        "fallback_line": fallback,
        "reply": fallback,
        "action_type": "MEMORY_EDIT_CANCEL",
    }


def confirm_pending_memory_edit() -> dict:
    payload = get_pending_memory_edit()
    if not payload:
        packet = {
            "tool": "manage_memory",
            "operation": "confirm",
            "status": "no_pending",
            "applied": False,
        }
        fallback = "Manage memory confirm: no pending change."
        return {
            "status": "no_pending",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MEMORY_EDIT_APPLIED",
        }
    manager_state.clear_pending_action(slot="memory")
    op = payload.get("operation")
    mid = payload.get("memory_id")
    if op == "delete":
        if not expire_memory_pg(mid).get("success"):
            packet = {
                "tool": "manage_memory",
                "operation": "delete",
                "status": "failed",
                "memory_id": mid,
                "applied": False,
                "reason": "postgres_unavailable_or_write_failed",
            }
            fallback = f"Manage memory delete failed for id={mid}."
            return {
                "status": "failed",
                "factual_packet": packet,
                "fallback_line": fallback,
                "reply": fallback,
                "action_type": "MEMORY_EDIT_APPLIED",
            }
        log_memory_event_pg(
            memory_id=mid, event_type="deleted_by_owner", metadata={"soft_delete": True}
        )
        packet = {
            "tool": "manage_memory",
            "operation": "delete",
            "status": "deleted",
            "memory_id": mid,
            "applied": True,
            "soft_delete": True,
        }
        fallback = f"Manage memory deleted (soft). id={mid}."
        return {
            "status": "deleted",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MEMORY_EDIT_APPLIED",
        }

    new_content = (payload.get("new_content") or "").strip()
    if not update_memory_content_pg(mid, new_content).get("success"):
        packet = {
            "tool": "manage_memory",
            "operation": "update",
            "status": "failed",
            "memory_id": mid,
            "applied": False,
            "reason": "postgres_unavailable_or_write_failed",
        }
        fallback = f"Manage memory update failed for id={mid}."
        return {
            "status": "failed",
            "factual_packet": packet,
            "fallback_line": fallback,
            "reply": fallback,
            "action_type": "MEMORY_EDIT_APPLIED",
        }
    emb_status = "skipped"
    try:
        from services.memory.embedding_provider import PRIMARY_EMBEDDING_MODEL, embed_text

        emb = embed_text(new_content)
        vec = emb.get("vector") or [] if emb.get("status") == "success" else []
        if len(vec) == _EMBEDDING_DIM:
            update_memory_embedding_pg(mid, PRIMARY_EMBEDDING_MODEL, vec)
            emb_status = "refreshed"
    except Exception:
        emb_status = "skipped"
    log_memory_event_pg(
        memory_id=mid, event_type="updated_by_owner", metadata={"embedding": emb_status}
    )
    packet = {
        "tool": "manage_memory",
        "operation": "update",
        "status": "updated",
        "memory_id": mid,
        "applied": True,
        "embedding": emb_status,
        "new_content": _clip(new_content, 140),
    }
    fallback = f"Manage memory updated. id={mid} embedding={emb_status}."
    return {
        "status": "updated",
        "factual_packet": packet,
        "fallback_line": fallback,
        "reply": fallback,
        "action_type": "MEMORY_EDIT_APPLIED",
    }


def try_confirm_or_cancel(msg_lower: str, message: str, tb, save_fn):
    """Brain hook: if a memory edit is pending, apply on affirmative / drop on rejection.

    Returns a finished result dict, or None if there is nothing pending to handle."""
    if not get_pending_memory_edit():
        return None
    from services.llm.intent_router import is_affirmative_reply, is_confirmation_only
    from services.memory.service import is_memory_rejection_message

    if is_memory_rejection_message(msg_lower):
        res = cancel_pending_memory_edit()
        tb.source = "local_router"
        tb.route = "memory_edit_cancel"
        return save_fn(
            message,
            res["reply"],
            action_type="MEMORY_EDIT_CANCEL",
            factual_packet=res.get("factual_packet"),
            _tb=tb,
        )
    if is_confirmation_only(msg_lower) or is_affirmative_reply(msg_lower):
        res = confirm_pending_memory_edit()
        tb.source = "local_router"
        tb.route = "memory_edit_applied"
        return save_fn(
            message,
            res["reply"],
            action_type="MEMORY_EDIT_APPLIED",
            factual_packet=res.get("factual_packet"),
            _tb=tb,
        )
    return None


__all__ = [
    "list_owner_memories_text",
    "build_owner_memories_list_packet",
    "create_pending_memory_edit",
    "get_pending_memory_edit",
    "cancel_pending_memory_edit",
    "confirm_pending_memory_edit",
    "try_confirm_or_cancel",
]

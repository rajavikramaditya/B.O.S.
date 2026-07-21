"""Self-change awareness — feel capability inventory diffs across restarts.

Not live body health (self_knowledge). Not curated seed text (self_narrative).
Deterministic fingerprint → diff → life episode → pending announce (facts only).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SELF_CHANGE_SCHEMA_VERSION = 1
FP_LATEST_DEDUPE = "neena_self_fp_latest"
FP_MEMORY_TYPE = "neena_mind_architecture"

# Primary inventory only — no capability_manifest.available_now (boot churn).
_FLAG_GETTERS: tuple[tuple[str, str], ...] = (
    ("NEENA_SMART_REPLY", "smart_reply_enabled"),
    ("NEENA_CONV_MEMORY", "conversation_memory_enabled"),
    ("NEENA_OWNER_WORKING_CONTEXT", "owner_working_context_enabled"),
    ("NEENA_SYSTEM_KNOWLEDGE_PACK", "system_knowledge_pack_enabled"),
    ("NEENA_BOUNDED_TOOL_LOOP", "bounded_tool_loop_enabled"),
    ("NEENA_DEEP_AGENT_LOOP", "deep_agent_loop_enabled"),
    ("NEENA_ONE_BRAIN_FOUNDATION", "one_brain_foundation_enabled"),
    ("NEENA_CUSTOMER_SALIENT_MEMORY", "customer_salient_memory_enabled"),
    ("NEENA_MEMORY_SOFT_FADE", "memory_soft_fade_enabled"),
    ("NEENA_SELF_CHANGE_AWARENESS", "self_change_awareness_enabled"),
)


def build_self_fingerprint() -> dict[str, Any]:
    """Stable sorted inventory of tools + flags + architecture seed keys."""
    tools: list[dict[str, Any]] = []
    try:
        from services.tools.catalog import all_specs

        for spec in all_specs():
            tools.append(
                {
                    "id": spec.id,
                    "risk": spec.risk,
                    "route": spec.route,
                    "category": spec.category or "general",
                    "feature_flag": spec.feature_flag,
                    "label": (spec.capability_label or spec.description or spec.id)[:120],
                }
            )
    except Exception as exc:
        logger.warning("self_change tools fingerprint failed: %s", type(exc).__name__)
    tools.sort(key=lambda t: t["id"])

    flags: dict[str, bool] = {}
    try:
        import services.brain.feature_flags as ff

        for env_name, getter_name in _FLAG_GETTERS:
            fn = getattr(ff, getter_name, None)
            if callable(fn):
                flags[env_name] = bool(fn())
    except Exception as exc:
        logger.warning("self_change flags fingerprint failed: %s", type(exc).__name__)

    arch_keys: list[str] = []
    try:
        from services.memory.self_narrative import architecture_seed_dedupe_keys

        arch_keys = list(architecture_seed_dedupe_keys())
    except Exception as exc:
        logger.warning("self_change arch keys failed: %s", type(exc).__name__)

    fp = {
        "schema_version": SELF_CHANGE_SCHEMA_VERSION,
        "tools": tools,
        "flags": dict(sorted(flags.items())),
        "arch_seed_keys": sorted(arch_keys),
    }
    fp["digest"] = _digest_fingerprint(fp)
    return fp


def diff_fingerprints(prev: dict[str, Any] | None, curr: dict[str, Any] | None) -> dict[str, Any]:
    """Set/field diffs. Empty when equivalent digests or missing baseline."""
    prev = prev if isinstance(prev, dict) else {}
    curr = curr if isinstance(curr, dict) else {}
    if not prev:
        return {
            "has_changes": False,
            "baseline": True,
            "added_tools": [],
            "removed_tools": [],
            "changed_tools": [],
            "changed_flags": [],
            "added_arch_keys": [],
            "removed_arch_keys": [],
            "digest": (curr or {}).get("digest"),
            "prev_digest": None,
        }

    prev_tools = {t["id"]: t for t in (prev.get("tools") or []) if isinstance(t, dict) and t.get("id")}
    curr_tools = {t["id"]: t for t in (curr.get("tools") or []) if isinstance(t, dict) and t.get("id")}
    added_ids = sorted(set(curr_tools) - set(prev_tools))
    removed_ids = sorted(set(prev_tools) - set(curr_tools))
    changed_tools: list[dict[str, Any]] = []
    for tid in sorted(set(prev_tools) & set(curr_tools)):
        a, b = prev_tools[tid], curr_tools[tid]
        if (a.get("risk"), a.get("route"), a.get("category"), a.get("feature_flag")) != (
            b.get("risk"),
            b.get("route"),
            b.get("category"),
            b.get("feature_flag"),
        ):
            changed_tools.append({"id": tid, "before": a, "after": b})

    prev_flags = prev.get("flags") if isinstance(prev.get("flags"), dict) else {}
    curr_flags = curr.get("flags") if isinstance(curr.get("flags"), dict) else {}
    changed_flags: list[dict[str, Any]] = []
    for name in sorted(set(prev_flags) | set(curr_flags)):
        if prev_flags.get(name) != curr_flags.get(name):
            changed_flags.append(
                {"flag": name, "before": prev_flags.get(name), "after": curr_flags.get(name)}
            )

    prev_arch = set(prev.get("arch_seed_keys") or [])
    curr_arch = set(curr.get("arch_seed_keys") or [])
    added_arch = sorted(curr_arch - prev_arch)
    removed_arch = sorted(prev_arch - curr_arch)

    has = bool(
        added_ids or removed_ids or changed_tools or changed_flags or added_arch or removed_arch
    )
    return {
        "has_changes": has,
        "baseline": False,
        "added_tools": [
            {"id": i, "label": (curr_tools[i].get("label") or i)} for i in added_ids
        ],
        "removed_tools": [{"id": i, "label": (prev_tools[i].get("label") or i)} for i in removed_ids],
        "changed_tools": changed_tools,
        "changed_flags": changed_flags,
        "added_arch_keys": added_arch,
        "removed_arch_keys": removed_arch,
        "digest": curr.get("digest"),
        "prev_digest": prev.get("digest"),
        "next_abilities": [
            (curr_tools[i].get("label") or i) for i in added_ids
        ],
    }


def reconcile_on_boot() -> dict[str, Any]:
    """Load previous fingerprint, diff, persist current, maybe episode + pending."""
    import services.brain.feature_flags as ff

    if not ff.self_change_awareness_enabled():
        return {"ok": True, "skipped": True, "reason": "flag_off"}

    curr = build_self_fingerprint()
    prev = _load_previous_fingerprint()
    delta = diff_fingerprints(prev, curr)
    persist = _persist_fingerprint(curr)

    out: dict[str, Any] = {
        "ok": True,
        "digest": curr.get("digest"),
        "baseline": bool(delta.get("baseline")),
        "has_changes": bool(delta.get("has_changes")),
        "persist_ok": bool(persist.get("success")),
    }

    if delta.get("baseline") or not delta.get("has_changes"):
        _clear_pending_announce()
        out["pending"] = False
        return out

    episode = _write_change_episode(delta, curr)
    pending_payload = {
        "digest": delta.get("digest"),
        "prev_digest": delta.get("prev_digest"),
        "added_tools": delta.get("added_tools") or [],
        "removed_tools": delta.get("removed_tools") or [],
        "changed_tools": [
            {"id": c.get("id")} for c in (delta.get("changed_tools") or []) if isinstance(c, dict)
        ],
        "changed_flags": delta.get("changed_flags") or [],
        "added_arch_keys": delta.get("added_arch_keys") or [],
        "removed_arch_keys": delta.get("removed_arch_keys") or [],
        "next_abilities": delta.get("next_abilities") or [],
    }
    _set_pending_announce(pending_payload)
    out["pending"] = True
    out["episode_created"] = bool(episode.get("created"))
    out["episode_ok"] = bool(episode.get("success"))
    return out


def peek_pending_announce() -> dict[str, Any] | None:
    raw = _get_pending_announce()
    return raw if isinstance(raw, dict) and raw.get("digest") else None


def consume_pending_announce() -> dict[str, Any] | None:
    """Return pending packet once and clear Redis."""
    raw = peek_pending_announce()
    if not raw:
        return None
    _clear_pending_announce()
    return _announce_packet(raw)


def format_change_recall() -> dict[str, Any]:
    """Owner ask path — factual packet (recent pending or last saved digest)."""
    pending = peek_pending_announce()
    if pending:
        packet = _announce_packet(pending)
        packet["status"] = "pending_unannounced"
        line = _fallback_line(pending)
        return {
            "action_type": "SELF_CHANGE_STATUS",
            "fallback_line": line,
            "factual_packet": packet,
            "ok": True,
        }

    curr = build_self_fingerprint()
    prev = _load_previous_fingerprint()
    delta = diff_fingerprints(prev, curr) if prev else None
    packet = {
        "tool": "self_change_status",
        "status": "no_pending_change",
        "digest": curr.get("digest"),
        "tool_count": len(curr.get("tools") or []),
        "flag_count": len(curr.get("flags") or {}),
        "arch_key_count": len(curr.get("arch_seed_keys") or []),
        "has_changes_vs_stored": bool(delta and delta.get("has_changes")),
    }
    line = (
        f"Self-change status: no pending announce. "
        f"tools={packet['tool_count']} digest={(curr.get('digest') or '')[:12]}."
    )
    return {
        "action_type": "SELF_CHANGE_STATUS",
        "fallback_line": line,
        "factual_packet": packet,
        "ok": True,
    }


def maybe_prepend_boot_change_announce(
    *,
    owner_message: str,
    reply: str,
    factual_packet: dict[str, Any] | None = None,
    action_type: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Consume pending boot change and prepend humanized preface once.

    Does not invent Hinglish in this module — uses response_composer humanize.
    """
    try:
        import services.brain.feature_flags as ff

        if not ff.self_change_awareness_enabled():
            return reply, factual_packet
    except Exception:
        return reply, factual_packet

    if (action_type or "").upper() in ("SELF_CHANGE_STATUS", "SELF_CHANGE_ANNOUNCE"):
        return reply, factual_packet

    pending = peek_pending_announce()
    if not pending:
        return reply, factual_packet

    packet = consume_pending_announce()
    if not packet:
        return reply, factual_packet

    preface = _fallback_line(pending)
    try:
        from services.brain import response_composer

        preface = response_composer.maybe_humanize_report(
            owner_message,
            preface,
            "SELF_CHANGE_ANNOUNCE",
            concise=True,
            factual_packet=packet,
        )
    except Exception:
        pass

    preface = (preface or "").strip()
    body = (reply or "").strip()
    merged = f"{preface}\n\n{body}".strip() if preface and body else (preface or body)

    out_packet = dict(factual_packet) if isinstance(factual_packet, dict) else {}
    out_packet["self_change_announce"] = packet
    return merged, out_packet


# --- internals ------------------------------------------------------------------


def _digest_fingerprint(fp: dict[str, Any]) -> str:
    payload = {
        "schema_version": fp.get("schema_version"),
        "tools": [
            {
                "id": t.get("id"),
                "risk": t.get("risk"),
                "route": t.get("route"),
                "category": t.get("category"),
                "feature_flag": t.get("feature_flag"),
            }
            for t in (fp.get("tools") or [])
        ],
        "flags": fp.get("flags") or {},
        "arch_seed_keys": fp.get("arch_seed_keys") or [],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _announce_packet(pending: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": "self_change_announce",
        "status": "changed",
        "digest": pending.get("digest"),
        "prev_digest": pending.get("prev_digest"),
        "added_tools": pending.get("added_tools") or [],
        "removed_tools": pending.get("removed_tools") or [],
        "changed_tools": pending.get("changed_tools") or [],
        "changed_flags": pending.get("changed_flags") or [],
        "added_arch_keys": pending.get("added_arch_keys") or [],
        "removed_arch_keys": pending.get("removed_arch_keys") or [],
        "next_abilities": pending.get("next_abilities") or [],
    }


def _fallback_line(pending: dict[str, Any]) -> str:
    added = [t.get("id") for t in (pending.get("added_tools") or []) if isinstance(t, dict)]
    removed = [t.get("id") for t in (pending.get("removed_tools") or []) if isinstance(t, dict)]
    flags = [
        f"{c.get('flag')}:{c.get('before')}->{c.get('after')}"
        for c in (pending.get("changed_flags") or [])
        if isinstance(c, dict)
    ]
    abilities = pending.get("next_abilities") or []
    parts = [
        "Self-change detected after restart.",
        f"added_tools={added or 'none'}.",
        f"removed_tools={removed or 'none'}.",
    ]
    if flags:
        parts.append(f"changed_flags={flags}.")
    if abilities:
        parts.append(f"new_abilities={abilities}.")
    parts.append(f"digest={(pending.get('digest') or '')[:12]}.")
    return " ".join(parts)


def _write_change_episode(delta: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    digest = (delta.get("digest") or curr.get("digest") or "unknown").strip()
    lines = [
        "Capability inventory changed after restart.",
        f"digest={digest}",
        f"added_tools={[t.get('id') for t in (delta.get('added_tools') or [])]}",
        f"removed_tools={[t.get('id') for t in (delta.get('removed_tools') or [])]}",
        f"changed_flags={delta.get('changed_flags') or []}",
        f"added_arch_keys={delta.get('added_arch_keys') or []}",
        f"removed_arch_keys={delta.get('removed_arch_keys') or []}",
    ]
    try:
        from services.memory.self_narrative import record_life_milestone

        return record_life_milestone(
            title="Self-change",
            content="\n".join(lines),
            dedupe_key=f"neena_self_change_{digest}",
            with_embeddings=False,
        )
    except Exception as exc:
        logger.warning("self_change episode failed: %s", type(exc).__name__)
        return {"success": False, "reason": type(exc).__name__}


def _load_previous_fingerprint() -> dict[str, Any] | None:
    try:
        import services.brain.redis_state as rs

        got = rs.get_self_fingerprint()
        data = got.get("fingerprint") if got.get("success") else None
        if isinstance(data, dict) and data.get("digest"):
            return data
    except Exception:
        pass
    try:
        from services.memory.pg_repository import find_memory_pg_by_dedupe_key

        found = find_memory_pg_by_dedupe_key(FP_LATEST_DEDUPE) or {}
        row = found.get("memory") if found.get("success") else None
        if not isinstance(row, dict):
            return None
        content = (row.get("content") or "").strip()
        if not content:
            return None
        data = json.loads(content)
        return data if isinstance(data, dict) and data.get("digest") else None
    except Exception:
        return None


def _persist_fingerprint(fp: dict[str, Any]) -> dict[str, Any]:
    redis_ok = False
    try:
        import services.brain.redis_state as rs

        redis_ok = bool(rs.save_self_fingerprint(fp).get("success"))
    except Exception as exc:
        logger.warning("self_change redis persist failed: %s", type(exc).__name__)

    pg_ok = False
    try:
        from services.memory.pg_repository import (
            create_memory_pg_idempotent,
            find_memory_pg_by_dedupe_key,
            is_postgres_available,
            update_memory_content_pg,
        )

        if (is_postgres_available() or {}).get("available"):
            blob = json.dumps(fp, ensure_ascii=False, sort_keys=True)
            found = find_memory_pg_by_dedupe_key(FP_LATEST_DEDUPE) or {}
            row = found.get("memory") if found.get("success") else None
            if isinstance(row, dict) and row.get("id"):
                pg_ok = bool(update_memory_content_pg(int(row["id"]), blob).get("success"))
            else:
                res = create_memory_pg_idempotent(
                    write_dedupe_key=FP_LATEST_DEDUPE,
                    memory_type=FP_MEMORY_TYPE,
                    content=blob,
                    owner_confirmed=True,
                    importance=2,
                    source="system_self_change_fingerprint",
                    retention="permanent",
                    sensitivity_level="normal",
                    metadata={"section": "self_change", "title": "capability_fingerprint"},
                    actor_role="owner",
                    subject_key="owner",
                    salience=0.5,
                )
                pg_ok = bool(res.get("success"))
    except Exception as exc:
        logger.warning("self_change pg persist failed: %s", type(exc).__name__)

    return {"success": redis_ok or pg_ok, "redis": redis_ok, "postgres": pg_ok}


def _set_pending_announce(payload: dict[str, Any]) -> None:
    try:
        import services.brain.redis_state as rs

        rs.save_self_change_pending(payload)
    except Exception as exc:
        logger.warning("self_change pending set failed: %s", type(exc).__name__)


def _get_pending_announce() -> dict[str, Any] | None:
    try:
        import services.brain.redis_state as rs

        got = rs.get_self_change_pending()
        data = got.get("pending") if got.get("success") else None
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _clear_pending_announce() -> None:
    try:
        import services.brain.redis_state as rs

        rs.clear_self_change_pending()
    except Exception:
        pass


__all__ = [
    "SELF_CHANGE_SCHEMA_VERSION",
    "build_self_fingerprint",
    "diff_fingerprints",
    "reconcile_on_boot",
    "peek_pending_announce",
    "consume_pending_announce",
    "format_change_recall",
    "maybe_prepend_boot_change_announce",
]

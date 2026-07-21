"""Deferred WhatsApp status worker — one pending job, poll → notify_owner.

Not a twin brain: arms via catalog tool only; facts from catalog.execute.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_SESSION_KEY = "deferred_status_job"
_LOCAL_PATH = Path(
    os.environ.get("NEENA_DEFERRED_STATUS_FILE")
    or str(Path(__file__).resolve().parents[3] / "runtime" / "deferred_status_job.json")
)
_MAX_DELAY_SEC = 6 * 3600
_MIN_DELAY_SEC = 60
_DEFAULT_DELAY_SEC = 300


def deferred_status_enabled() -> bool:
    raw = (os.environ.get("NEENA_DEFERRED_STATUS") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_deferred_worker_ready() -> bool:
    return deferred_status_enabled()


def _now_ts() -> float:
    return time.time()


def _prefer_local_file() -> bool:
    return bool(os.environ.get("NEENA_DEFERRED_STATUS_FILE"))


def _read_job() -> dict[str, Any] | None:
    if _prefer_local_file():
        try:
            if _LOCAL_PATH.is_file():
                data = json.loads(_LOCAL_PATH.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else None
        except Exception:
            return None
        return None
    try:
        from services.brain.redis_state import get_session_state

        got = get_session_state(_SESSION_KEY)
        raw = got.get("value") if got.get("success") else None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    try:
        if _LOCAL_PATH.is_file():
            data = json.loads(_LOCAL_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        pass
    return None


def _write_job(job: dict[str, Any] | None) -> bool:
    if _prefer_local_file():
        try:
            _LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            if job is None:
                if _LOCAL_PATH.is_file():
                    _LOCAL_PATH.unlink()
            else:
                _LOCAL_PATH.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            logger.warning("[deferred_status] local write failed: %s", exc)
            return False
    ok = False
    try:
        from services.brain.redis_state import delete_session_state, set_session_state

        if job is None:
            delete_session_state(_SESSION_KEY)
            ok = True
        else:
            res = set_session_state(
                _SESSION_KEY,
                json.dumps(job, ensure_ascii=False),
                ttl_seconds=_MAX_DELAY_SEC + 3600,
            )
            ok = bool(res.get("success"))
    except Exception as exc:
        logger.debug("[deferred_status] redis write skip: %s", exc)
    try:
        _LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        if job is None:
            if _LOCAL_PATH.is_file():
                _LOCAL_PATH.unlink()
            ok = True
        else:
            _LOCAL_PATH.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
            ok = True
    except Exception as exc:
        logger.warning("[deferred_status] local write failed: %s", exc)
    return ok


def get_pending_job() -> dict[str, Any] | None:
    job = _read_job()
    if not job or job.get("status") not in ("armed", "due", "delivering"):
        return None
    return job


def parse_delay_seconds(message: str, slots: dict[str, Any] | None = None) -> int:
    slots = slots or {}
    if slots.get("delay_seconds") is not None:
        try:
            return max(_MIN_DELAY_SEC, min(_MAX_DELAY_SEC, int(slots["delay_seconds"])))
        except (TypeError, ValueError):
            pass
    if slots.get("delay_minutes") is not None:
        try:
            return max(_MIN_DELAY_SEC, min(_MAX_DELAY_SEC, int(float(slots["delay_minutes"]) * 60)))
        except (TypeError, ValueError):
            pass
    msg = (message or "").lower()
    if re.search(r"\bpaanch\s*min", msg):
        return 300
    m = re.search(r"\b(\d+)\s*(min|minute|minutes|mins)\b", msg)
    if m:
        return max(_MIN_DELAY_SEC, min(_MAX_DELAY_SEC, int(m.group(1)) * 60))
    return _DEFAULT_DELAY_SEC


def parse_status_kind(message: str, slots: dict[str, Any] | None = None) -> str:
    slots = slots or {}
    kind = str(slots.get("status_kind") or "").strip().lower()
    if kind in ("vm_status", "now_playing", "station_status", "bundle"):
        return kind
    msg = (message or "").lower()
    if "vm" in msg or "body" in msg or "cpu" in msg:
        return "vm_status"
    if "now playing" in msg or "kya chal" in msg:
        return "now_playing"
    return "bundle"


def arm_deferred_status(
    *,
    message: str,
    slots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not deferred_status_enabled():
        return {
            "ok": False,
            "status": "cannot",
            "reason": "deferred_followthrough_not_armed",
            "detail": "NEENA_DEFERRED_STATUS off",
        }
    with _LOCK:
        existing = get_pending_job()
        if existing and existing.get("status") in ("armed", "due", "delivering"):
            return {
                "ok": False,
                "status": "busy",
                "reason": "pending_deferred_exists",
                "existing_job_id": existing.get("job_id"),
                "due_at": existing.get("due_at_iso") or existing.get("due_at"),
                "detail": "Max 1 pending deferred status job",
            }
        delay = parse_delay_seconds(message, slots)
        kind = parse_status_kind(message, slots)
        due_at = _now_ts() + delay
        job = {
            "job_id": str(uuid.uuid4())[:12],
            "status": "armed",
            "status_kind": kind,
            "delay_seconds": delay,
            "due_at": due_at,
            "due_at_iso": datetime.fromtimestamp(due_at, tz=timezone.utc).isoformat(),
            "owner_message": (message or "")[:300],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "channel": "whatsapp",
        }
        if not _write_job(job):
            return {
                "ok": False,
                "status": "cannot",
                "reason": "deferred_store_failed",
                "detail": "could not persist deferred job",
            }
        return {
            "ok": True,
            "status": "armed",
            "job_id": job["job_id"],
            "status_kind": kind,
            "delay_seconds": delay,
            "due_at": job["due_at_iso"],
            "channel": "whatsapp",
            "worker": "deferred_status",
            "neena_role": "separate_agent_product",
        }


def _build_fact_lines(kind: str) -> str:
    lines: list[str] = []
    try:
        from services.tools.catalog import ToolContext, execute
        from services.tools import load_all

        load_all()
        ids = ["now_playing", "vm_status"] if kind == "bundle" else [kind if kind != "bundle" else "now_playing"]
        if kind == "station_status":
            ids = ["station_status"]
        elif kind == "vm_status":
            ids = ["vm_status"]
        elif kind == "now_playing":
            ids = ["now_playing"]
        for tid in ids:
            try:
                ctx = ToolContext(action=tid, slots={}, snapshot={}, owner_message="deferred_tick")
                out = execute(tid, ctx)
                if isinstance(out, dict):
                    reply = (out.get("reply") or "").strip()
                    if reply:
                        lines.append(reply[:400])
                    else:
                        fp = out.get("factual_packet") if isinstance(out.get("factual_packet"), dict) else {}
                        if fp:
                            lines.append(json.dumps(fp, ensure_ascii=False)[:400])
            except Exception as exc:
                lines.append(f"{tid}: unavailable ({type(exc).__name__})")
    except Exception as exc:
        lines.append(f"fact_gather_failed:{type(exc).__name__}")
    if not lines:
        lines.append("Deferred status tick: no tool facts available.")
    return "\n".join(lines)


def tick_once(*, force_due: bool = False) -> dict[str, Any] | None:
    if not deferred_status_enabled():
        return None
    with _LOCK:
        job = _read_job()
        if not job or job.get("status") not in ("armed", "due"):
            return None
        due_at = float(job.get("due_at") or 0)
        if not force_due and _now_ts() < due_at:
            return None
        job["status"] = "delivering"
        _write_job(job)
        kind = str(job.get("status_kind") or "bundle")
        job_id = job.get("job_id")
    body = _build_fact_lines(kind)
    msg = f"[Neena deferred status — job {job_id}]\nKind={kind}. Fresh facts:\n{body}"
    delivered = False
    try:
        from services.brain.owner_notifier import notify_owner

        delivered = bool(notify_owner(msg))
    except Exception as exc:
        logger.warning("[deferred_status] notify failed: %s", exc)
    with _LOCK:
        final = {
            **job,
            "status": "delivered" if delivered else "failed",
            "delivered": delivered,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
            "message_preview": msg[:200],
        }
        _write_job(None)
        try:
            result_path = _LOCAL_PATH.with_name("deferred_status_last.json")
            result_path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return final


async def start_deferred_status_loop(poll_seconds: float = 15.0) -> None:
    import asyncio

    if not deferred_status_enabled():
        logger.info("[deferred_status] disabled (NEENA_DEFERRED_STATUS off)")
        return
    logger.info("[deferred_status] poller started poll=%.0fs", poll_seconds)
    while True:
        try:
            tick_once()
        except Exception as exc:
            logger.warning("[deferred_status] tick error: %s", exc)
        await asyncio.sleep(max(5.0, float(poll_seconds)))


__all__ = [
    "arm_deferred_status",
    "deferred_status_enabled",
    "get_pending_job",
    "is_deferred_worker_ready",
    "parse_delay_seconds",
    "start_deferred_status_loop",
    "tick_once",
]

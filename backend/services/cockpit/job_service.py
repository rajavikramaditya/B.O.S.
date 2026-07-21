"""M4-A8.3 — Cockpit background jobs: orchestration (thread pool + follow-through).

Data access (all SQL for `cockpit_jobs`) lives in `cockpit_job_repository.py`.
This module keeps the public job API stable (re-exported from the repository)
and owns the runtime orchestration: worker pool, job runners, and server-side
owner follow-through.
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import services.cockpit.job_repository as repo
# Backward-compatible public data API (callers import these from this module).
from services.cockpit.job_repository import (  # noqa: F401
    JOB_STATUSES,
    ensure_cockpit_jobs_table,
    find_active_job_for_action,
    get_job,
    list_active_jobs,
    list_unseen_finished_jobs,
    mark_failed,
    mark_owner_seen,
    mark_running,
    mark_succeeded,
    update_progress,
)

_MAX_WORKERS = 2
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="cockpit_job")
_lock = threading.Lock()
_running_by_action: dict[str, str] = {}

_START_MESSAGES = {
    "verify_latest_stream": (
        "Stream verification start kar di hai. Result aate hi bataungi."
    ),
}


def create_job(action: str, payload: dict[str, Any] | None = None) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    repo.insert_job(job_id, action, payload)
    return job_id


def _push_job_result_to_owner(action: str, status: str, owner_message: str | None) -> None:
    """Best-effort server-initiated WhatsApp delivery of a finished long job."""
    try:
        import services.brain.feature_flags as feature_flags

        if not feature_flags.job_whatsapp_push_enabled():
            return
        if not owner_message:
            return
        from services.brain.owner_notifier import notify_owner

        labels = {
            "verify_latest_stream": "Stream verification",
        }
        label = labels.get(action) or (action or "Background job").replace("_", " ")
        prefix = (
            f"{label} result:"
            if status == "succeeded"
            else f"{label} finished with issue:"
        )
        notify_owner(f"{prefix}\n\n{owner_message}")
    except Exception as exc:  # pragma: no cover - best effort
        import logging

        logging.getLogger(__name__).warning("[cockpit_job] owner push failed: %s", exc)


def _run_verify_latest_stream(job_id: str, watch_seconds: int) -> None:
    t0 = time.monotonic()
    mark_running(job_id, "Stream verification start…")
    try:
        from services.broadcast.capsule_service import list_recent_capsules
        from services.broadcast.stream_verification import verify_capsule_stream_status

        capsules = list_recent_capsules(limit=5)
        if not capsules:
            mark_failed(
                job_id,
                "no_capsule",
                owner_message="Verify ke liye koi capsule nahi mila.",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return

        cap_id = int(capsules[0].get("id"))
        update_progress(job_id, "AzuraCast now-playing check…", {"capsule_id": cap_id})
        result = verify_capsule_stream_status(
            cap_id, watch_seconds=max(0, min(int(watch_seconds or 0), 60))
        )
        message = (
            result.get("message")
            or result.get("verification_status")
            or "Stream verify complete."
        )
        status = result.get("verification_status") or "verify_done"
        if status == "verified":
            progress = "Stream verified"
        elif result.get("success"):
            progress = "Verify complete"
        else:
            progress = "Uploaded but not currently playing"
        update_progress(job_id, progress)
        mark_succeeded(
            job_id,
            message,
            {
                "capsule_id": cap_id,
                "verification_status": status,
                "success": result.get("success"),
            },
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:
        mark_failed(
            job_id,
            type(exc).__name__,
            owner_message="Stream verify fail ho gaya — thodi der baad dubara try kariye.",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    finally:
        with _lock:
            _running_by_action.pop("verify_latest_stream", None)


def _dispatch_worker(job_id: str, action: str, payload: dict[str, Any]) -> None:
    if action == "verify_latest_stream":
        _run_verify_latest_stream(job_id, int(payload.get("watch_seconds") or 30))
    else:
        mark_failed(job_id, "unsupported_action", owner_message=f"Unknown job action: {action}")
        return

    # Server-initiated follow-through: push the finished result to the owner's
    # WhatsApp so it is not lost if the web tab closed / poll window expired.
    final = get_job(job_id) or {}
    if final.get("status") in ("succeeded", "failed"):
        _push_job_result_to_owner(action, final.get("status"), final.get("owner_message"))


def submit_background_job(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Queue a long cockpit action; returns quickly with job_id."""
    action = (action or "").strip().lower()
    if action == "diagnostics_deep":
        return {
            "ok": False,
            "action": action,
            "mode": "rejected",
            "message": "Deep diagnostics hata diya gaya hai — fast diagnostics use kariye.",
            "latency_ms": 0,
            "gemini_calls": 0,
        }
    payload = dict(payload or {})
    t0 = time.monotonic()
    with _lock:
        existing = find_active_job_for_action(action)
        if existing:
            return {
                "ok": True,
                "action": action,
                "mode": "background",
                "job_id": existing,
                "message": _START_MESSAGES.get(action, "Background job already running."),
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "reused": True,
            }
        job_id = create_job(action, payload)
        _running_by_action[action] = job_id

    _executor.submit(_dispatch_worker, job_id, action, payload)
    return {
        "ok": True,
        "action": action,
        "mode": "background",
        "job_id": job_id,
        "message": _START_MESSAGES.get(action, "Background job start ho gayi."),
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "gemini_calls": 0,
    }


ensure_cockpit_jobs_table()

__all__ = [
    "create_job",
    "find_active_job_for_action",
    "get_job",
    "list_active_jobs",
    "list_unseen_finished_jobs",
    "mark_failed",
    "mark_owner_seen",
    "mark_running",
    "mark_succeeded",
    "submit_background_job",
    "update_progress",
]

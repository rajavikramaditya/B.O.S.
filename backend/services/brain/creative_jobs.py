"""M4-A8.5 — Background creative command jobs (reuse cockpit_jobs)."""
from __future__ import annotations

import logging
import time
from typing import Any

from services.cockpit.job_service import (
    create_job,
    get_job,
    mark_failed,
    mark_running,
    mark_succeeded,
    update_progress,
)
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="creative_job")

def _clip_owner_msg(text: str, limit: int = 3500) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 20] + "\n\n…(truncated)"


def _push_creative_result_to_owner(job_id: str, job_action: str) -> None:
    """Server-initiated follow-through — do not go silent after 'queue ho gayi'."""
    try:
        import services.brain.feature_flags as feature_flags

        if not feature_flags.job_whatsapp_push_enabled():
            return
        final = get_job(job_id) or {}
        status = (final.get("status") or "").strip().lower()
        if status not in ("succeeded", "failed"):
            return
        body = (final.get("owner_message") or "").strip()
        if not body and status == "failed":
            body = final.get("error_summary") or "Creative job fail ho gaya."
        if not body:
            return
        from services.brain.owner_notifier import notify_owner

        label = (job_action or "creative_job").replace("creative_", "").replace("_", " ")
        if status == "succeeded":
            prefix = f"{label} complete (job `{job_id}`):"
        else:
            prefix = f"{label} failed / issue (job `{job_id}`):"
        ok = notify_owner(f"{prefix}\n\n{_clip_owner_msg(body)}")
        if not ok:
            logger.warning("[creative_job] owner WhatsApp push failed job_id=%s", job_id)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("[creative_job] owner push error: %s", type(exc).__name__)


def _run_creative_job(
    job_id: str,
    message: str,
    interpreter_packet: dict,
    selected_model: str,
) -> None:
    t0 = time.monotonic()
    job_action = f"creative_{(interpreter_packet.get('action') or 'unknown').strip().lower()}"
    mark_running(job_id, "Creative generation chal rahi hai…")
    try:
        from services.brain.live_state_snapshot import build_neena_live_state_snapshot
        from services.brain.load_shedding import is_load_critical

        while is_load_critical(build_neena_live_state_snapshot()):
            update_progress(job_id, "System load high — creative job queue me wait kar rahi hoon…")
            time.sleep(5)

        import services.memory.service as memory_service
        from services.brain.operations_workflows import try_handle_interpreter_packet
        from services.brain.trace_builder import _TraceBuilder as NeenaTraceBuilder

        tb = NeenaTraceBuilder()
        mem_packet = memory_service.get_memory_context_packet(message)
        mem_context = mem_packet.get("context_text") or ""
        update_progress(job_id, "Model generation…")
        result = try_handle_interpreter_packet(
            message=message,
            interpreter_packet=interpreter_packet,
            selected_model=selected_model,
            mem_packet=mem_packet,
            mem_context=mem_context,
            tb=tb,
            force_sync=True,
        )
        if not result or not result.get("reply"):
            mark_failed(
                job_id,
                "generation_empty",
                owner_message="Creative generation fail — dubara try kariye.",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return
        mark_succeeded(
            job_id,
            result.get("reply", "")[:4000],
            {
                "action_type": result.get("action_type"),
                "capsule_id": result.get("capsule_id"),
                "approval_id": result.get("approval_id"),
            },
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:
        logger.exception("creative job failed:")
        mark_failed(
            job_id,
            type(exc).__name__,
            owner_message=f"Creative command fail: {type(exc).__name__}. Local status abhi bhi available hai.",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    finally:
        _push_creative_result_to_owner(job_id, job_action)


def enqueue_creative_command_job(
    message: str,
    interpreter_packet: dict,
    selected_model: str = "auto",
) -> dict[str, Any]:
    action = (interpreter_packet.get("action") or "unknown").strip().lower()
    job_action = f"creative_{action}"
    t0 = time.monotonic()
    job_id = create_job(
        job_action,
        {"message": message, "packet": interpreter_packet, "model": selected_model},
    )
    _executor.submit(_run_creative_job, job_id, message, interpreter_packet, selected_model)
    factual = {
        "tool": "creative_job",
        "status": "queued",
        "job_id": job_id,
        "action": job_action,
    }
    return {
        "ok": True,
        "mode": "background",
        "job_id": job_id,
        "action": job_action,
        "message": (
            f"Creative job queued. action={job_action}. job_id={job_id}. "
            "Result will push when complete."
        ),
        "factual_packet": factual,
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "gemini_calls": 0,
    }


__all__ = ["enqueue_creative_command_job"]

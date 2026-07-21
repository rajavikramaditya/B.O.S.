"""Phase 4 — Command Center agent UX APIs (working context + feature flags).

Owner-facing read/toggle surfaces for Cursor-like CC. No secrets.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/neena", tags=["neena-agent-ux"])


class FeatureFlagPatch(BaseModel):
    flag: str = Field(..., min_length=3, max_length=80)
    enabled: Optional[bool] = None  # None = clear override (env default)


def _public_working_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Sanitize scratchpad for UI (clip strings; no prompts/secrets)."""
    pending = ctx.get("pending") if isinstance(ctx.get("pending"), dict) else None
    recent = ctx.get("recent_actions") if isinstance(ctx.get("recent_actions"), list) else []
    recent_out = []
    for item in recent[-5:]:
        if not isinstance(item, dict):
            continue
        recent_out.append(
            {
                "action_type": str(item.get("action_type") or "")[:80] or None,
                "route": str(item.get("route") or "")[:80] or None,
                "ts": str(item.get("ts") or "")[:40] or None,
            }
        )
    return {
        "open_goal": str(ctx.get("open_goal") or "")[:160] or None,
        "last_action_type": str(ctx.get("last_action_type") or "")[:80] or None,
        "last_route": str(ctx.get("last_route") or "")[:80] or None,
        "last_user_message": str(ctx.get("last_user_message") or "")[:160] or None,
        "last_assistant_reply": str(ctx.get("last_assistant_reply") or "")[:200] or None,
        "last_job_id": str(ctx.get("last_job_id") or "")[:80] or None,
        "last_capsule_id": str(ctx.get("last_capsule_id") or "")[:80] or None,
        "pending": (
            {
                "action_type": str(pending.get("action_type") or "")[:80] or None,
                "memory_id": pending.get("memory_id"),
                "capsule_id": pending.get("capsule_id"),
                "operation": str(pending.get("operation") or "")[:40] or None,
                "status": str(pending.get("status") or "")[:60] or None,
            }
            if pending
            else None
        ),
        "recent_actions": recent_out,
        "updated_at": str(ctx.get("updated_at") or "")[:40] or None,
    }


@router.get("/working-context")
def get_working_context():
    """Read-only owner working context for CC thread strip."""
    import services.brain.feature_flags as feature_flags
    from services.agent.working_context import load_working_context

    enabled = feature_flags.owner_working_context_enabled()
    if not enabled:
        return {"ok": True, "enabled": False, "context": {}}
    raw = load_working_context()
    return {
        "ok": True,
        "enabled": True,
        "context": _public_working_context(raw) if raw else {},
    }


@router.get("/feature-flags")
def get_feature_flags():
    """Snapshot of Phase 4 agent flags (+ override state)."""
    import services.brain.feature_flags as feature_flags

    return feature_flags.snapshot_agent_flags()


@router.patch("/feature-flags")
def patch_feature_flags(data: FeatureFlagPatch):
    """Toggle a CC-allowlisted flag override (or clear with enabled=null)."""
    import services.brain.feature_flags as feature_flags

    result = feature_flags.set_flag_override(data.flag, data.enabled)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "bad_flag")
    return result


class StationPlanCreate(BaseModel):
    horizon: str = "shift_4h"
    theme: str = ""
    hours: Optional[int] = None


class StationPlanDraft(BaseModel):
    block_id: Optional[str] = None


@router.get("/station-plan")
def get_station_plan_api():
    """Active Station Clock plan for Lab card."""
    from services.tools.station_plan_store import load_plan

    plan = load_plan()
    return {"ok": True, "plan": plan, "empty": plan is None}


@router.post("/station-plan")
def create_station_plan_api(data: StationPlanCreate):
    from services.tools.catalog import ToolContext
    from services.tools.station_plan import _handle_create

    ctx = ToolContext(
        action="create_station_plan",
        slots={"horizon": data.horizon, "theme": data.theme, "hours": data.hours},
        snapshot={},
        owner_message=f"Create {data.horizon} station plan",
    )
    out = _handle_create(ctx) or {}
    pkt = out.get("factual_packet") if isinstance(out.get("factual_packet"), dict) else {}
    return {
        "ok": pkt.get("status") == "ok",
        "reply": out.get("reply"),
        "plan": pkt.get("plan"),
        "action_type": out.get("action_type"),
    }


@router.post("/station-plan/draft-next")
def draft_station_plan_block_api(data: StationPlanDraft):
    from services.tools.catalog import ToolContext
    from services.tools.station_plan import _handle_draft

    slots: dict[str, Any] = {}
    if data.block_id:
        slots["block_id"] = data.block_id
    ctx = ToolContext(
        action="draft_plan_block",
        slots=slots,
        snapshot={},
        owner_message="Draft next station plan block",
    )
    out = _handle_draft(ctx) or {}
    pkt = out.get("factual_packet") if isinstance(out.get("factual_packet"), dict) else {}
    return {
        "ok": pkt.get("status") in ("ok", "partial"),
        "reply": out.get("reply"),
        "capsule_id": pkt.get("capsule_id"),
        "block_id": pkt.get("block_id"),
        "factual_packet": pkt,
    }

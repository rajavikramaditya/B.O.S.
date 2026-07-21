"""Redis (or in-process) store for living Station Clock plan — not a capsule."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")
_KEY = "neena:live:station_plan"
_TTL = 36 * 3600
_FALLBACK: dict[str, Any] = {}


def _now_ist() -> datetime:
    return datetime.now(_IST)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def load_plan() -> dict[str, Any] | None:
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            raw = client.get(_KEY)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("plan_id"):
                    _FALLBACK.clear()
                    _FALLBACK.update(data)
                    return dict(data)
    except Exception as exc:
        logger.debug("station_plan redis load: %s", exc)
    if _FALLBACK.get("plan_id"):
        return dict(_FALLBACK)
    return None


def save_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan = dict(plan)
    plan["updated_at"] = _iso(_now_ist())
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            client.setex(_KEY, _TTL, json.dumps(plan, ensure_ascii=False, default=str))
    except Exception as exc:
        logger.debug("station_plan redis save: %s", exc)
    _FALLBACK.clear()
    _FALLBACK.update(plan)
    return plan


def clear_plan() -> None:
    try:
        from services.brain import redis_state

        client = redis_state._client()
        if client is not None:
            client.delete(_KEY)
    except Exception:
        pass
    _FALLBACK.clear()


def build_shift_clock_plan(
    *,
    horizon: str = "shift_4h",
    hours: int | None = None,
    start: datetime | None = None,
    theme: str = "",
) -> dict[str, Any]:
    """Deterministic Radio Clock blocks for next N hours (talk links, not music)."""
    h = hours
    if h is None:
        h = 4 if horizon in ("shift_4h", "shift_3h", "shift") else 4
        if horizon == "shift_3h":
            h = 3
        if horizon == "day":
            h = 8  # chunked day — not 24h dump
    h = max(1, min(int(h), 12))
    start = start or _now_ist().replace(minute=0, second=0, microsecond=0)
    if start.tzinfo is None:
        start = start.replace(tzinfo=_IST)
    blocks: list[dict[str, Any]] = []
    kinds_cycle = ("rj_intro", "comedy", "ad", "mandi_or_local", "teaser")
    for hour_i in range(h):
        hour_start = start + timedelta(hours=hour_i)
        for slot_i, (offset_min, dur, kind) in enumerate(
            (
                (12, 3, kinds_cycle[hour_i % len(kinds_cycle)]),
                (28, 3, "ad" if hour_i % 2 == 0 else "comedy"),
                (48, 4, "teaser" if hour_i == h - 1 else "rj_intro"),
            )
        ):
            b_start = hour_start + timedelta(minutes=offset_min)
            b_end = b_start + timedelta(minutes=dur)
            bid = f"b{hour_i}_{slot_i}_{uuid.uuid4().hex[:6]}"
            title = {
                "rj_intro": f"RJ link {hour_start.strftime('%H:%M')}",
                "comedy": f"Comedy break {hour_start.strftime('%H:%M')}",
                "ad": f"Ad slot {hour_start.strftime('%H:%M')}",
                "mandi_or_local": f"Local/mandi update {hour_start.strftime('%H:%M')}",
                "teaser": f"Next-hour teaser {hour_start.strftime('%H:%M')}",
            }.get(kind, kind)
            if theme:
                title = f"{theme}: {title}"
            blocks.append(
                {
                    "id": bid,
                    "start": _iso(b_start),
                    "end": _iso(b_end),
                    "title": title,
                    "kind": kind,
                    "status": "pending",
                    "capsule_id": None,
                    "notes": "AutoDJ music fills gaps; this block = talk link only",
                }
            )
    end = start + timedelta(hours=h)
    return {
        "plan_id": f"sp_{uuid.uuid4().hex[:10]}",
        "horizon": horizon if horizon != "shift" else f"shift_{h}h",
        "date_ist": start.strftime("%Y-%m-%d"),
        "window_start": _iso(start),
        "window_end": _iso(end),
        "theme": (theme or "")[:120],
        "status": "active",
        "blocks": blocks,
        "created_at": _iso(_now_ist()),
        "updated_at": _iso(_now_ist()),
    }


def next_pending_block(plan: dict[str, Any]) -> dict[str, Any] | None:
    for b in plan.get("blocks") or []:
        if isinstance(b, dict) and b.get("status") == "pending":
            return b
    return None


def patch_block(
    plan: dict[str, Any],
    block_id: str,
    *,
    status: str | None = None,
    capsule_id: Any = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    for b in plan.get("blocks") or []:
        if not isinstance(b, dict) or b.get("id") != block_id:
            continue
        if status:
            b["status"] = status
        if capsule_id is not None:
            b["capsule_id"] = capsule_id
        if notes is not None:
            b["notes"] = notes[:300]
        return b
    return None


__all__ = [
    "build_shift_clock_plan",
    "clear_plan",
    "load_plan",
    "next_pending_block",
    "patch_block",
    "save_plan",
]

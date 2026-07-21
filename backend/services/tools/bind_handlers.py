"""Bind concrete handlers onto catalog ToolSpecs (cockpit / prefs / live_ops package)."""
from __future__ import annotations

from typing import Any

from services.tools.catalog import ToolContext, set_handler


def _cockpit_handler(action_id: str):
    def _handle(ctx: ToolContext) -> dict[str, Any] | None:
        from services.cockpit.action_service import execute_cockpit_action_for_chat

        got = execute_cockpit_action_for_chat(action_id, ctx.slots)
        return got if isinstance(got, dict) else None

    return _handle


def _minutes_until_morning_ist(ist: "datetime", *, morning_hour: int = 6) -> int:
    """Minutes from ist until next local morning_hour:00 (default 06:00 IST)."""
    from datetime import timedelta

    target = ist.replace(hour=int(morning_hour), minute=0, second=0, microsecond=0)
    if ist >= target:
        target = target + timedelta(days=1)
    return max(0, int((target - ist).total_seconds() // 60))


def _time_status_handler(ctx: ToolContext) -> dict[str, Any] | None:
    from datetime import datetime, timedelta, timezone

    from services.brain.factual_reply import build_live_ops_result

    del ctx
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    mins = _minutes_until_morning_ist(ist, morning_hour=6)
    hours = round(mins / 60.0, 2)
    packet = {
        "tool": "time_status",
        "status": "ok",
        "ist": ist.isoformat(),
        "now_ist": ist.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ist.strftime("%A"),
        "morning_local_hour": 6,
        "minutes_until_local_morning": mins,
        "hours_until_morning": hours,
    }
    # Factual fallback only — conversation/humanize owns owner Hinglish (no canned Sir).
    line = (
        f"Now IST={packet['now_ist']} ({packet['weekday']}). "
        f"minutes_until_local_morning={mins} (06:00 IST). "
        f"hours_until_morning={hours}."
    )
    return build_live_ops_result(
        "TIME_STATUS",
        packet=packet,
        fallback_line=line,
    )


def bind_all() -> None:
    from services.tools.live_ops import bind_all as bind_live_ops

    bind_live_ops()
    set_handler("station_status", _cockpit_handler("station_status"))
    set_handler("diagnostics", _cockpit_handler("diagnostics"))
    set_handler("time_status", _time_status_handler)


__all__ = ["bind_all"]

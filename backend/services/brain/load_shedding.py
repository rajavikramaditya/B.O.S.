"""M4-A8.5 — System load shedding for model/creative jobs."""
from __future__ import annotations

from typing import Any


def get_system_load(snapshot: dict[str, Any] | None) -> tuple[float, float]:
    stats = (snapshot or {}).get("local_stats") or {}
    return float(stats.get("cpu") or 0), float(stats.get("ram") or 0)


def is_load_high(snapshot: dict[str, Any] | None, threshold: float = 85.0) -> bool:
    cpu, ram = get_system_load(snapshot)
    return cpu > threshold or ram > threshold


def is_load_critical(snapshot: dict[str, Any] | None, threshold: float = 95.0) -> bool:
    cpu, ram = get_system_load(snapshot)
    return cpu > threshold or ram > threshold


def build_load_defer_reply(snapshot: dict[str, Any] | None, *, threshold: float = 85.0) -> str:
    cpu, ram = get_system_load(snapshot)
    over = []
    if cpu > threshold:
        over.append(f"CPU {cpu:.0f}%")
    if ram > threshold:
        over.append(f"RAM {ram:.0f}%")
    load_txt = " aur ".join(over) if over else f"CPU {cpu:.0f}% / RAM {ram:.0f}%"
    return (
        f"Load shed: {load_txt} above threshold {threshold:.0f}%. "
        f"Creative generation deferred (not queued). Retry when CPU/RAM below {threshold:.0f}%. "
        "Local status/capabilities/memory tools still available."
    )


def build_load_defer_payload(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    cpu, ram = get_system_load(snapshot)
    return {
        "reply": build_load_defer_reply(snapshot),
        "action_type": "LOAD_SHED_DEFER",
        "blocked": True,
        "ok": False,
        "queued": False,
        "defer_status": "deferred_due_load",
        "load_status": {
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(ram, 1),
            "threshold_percent": 85.0,
            "retry_when": "ram_or_cpu_below_85",
        },
        "gemini_calls": 0,
        "mode": "local",
    }


def build_load_block_reply(snapshot: dict[str, Any] | None) -> str:
    return build_load_defer_reply(snapshot)


__all__ = [
    "build_load_block_reply",
    "build_load_defer_payload",
    "build_load_defer_reply",
    "get_system_load",
    "is_load_critical",
    "is_load_high",
]

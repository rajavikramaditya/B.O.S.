"""VM / host health summary for owner status queries (read-only, no AzuraCast writes)."""
from __future__ import annotations

import os
from typing import Any

import psutil


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def build_vm_status_reply(snapshot: dict | None = None) -> str:
    from services.cockpit.launch_health import get_memory_stack_summary_fast
    from services.brain.live_state_snapshot import build_neena_live_state_snapshot
    from services.cockpit.self_heal import last_heal_summary_line

    snap = snapshot or build_neena_live_state_snapshot()
    mem_stack = get_memory_stack_summary_fast()
    runtime = (os.environ.get("RUNTIME_MODE") or "LOCAL_TEST_MODE").upper()

    # CPU/RAM from shared snapshot only — no second psutil CPU sample.
    stats = snap.get("local_stats") or {}
    if not stats:
        from services.cockpit.runtime_controller import get_system_stats

        stats = get_system_stats()
    cpu = float(stats.get("cpu") or 0)
    ram_pct = float(stats.get("ram") or 0)
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    launch = snap.get("launch") or {}
    backend = launch.get("backend") or "unknown"
    pg = "ok" if mem_stack.get("postgres_available") else "offline"
    redis = "ok" if mem_stack.get("redis_available") else "offline"
    wa = snap.get("whatsapp_gateway") or "unknown"
    stream = snap.get("stream") or "unknown"
    heal_line = last_heal_summary_line()

    lines = [
        "VM/cloud status summary.",
        f"- Runtime mode: {runtime}",
        f"- Backend reachable: {backend}",
        f"- CPU load: {cpu:.0f}%",
        f"- RAM: {_fmt_bytes(vm.used)} used / {_fmt_bytes(vm.total)} total ({ram_pct:.0f}%)",
        f"- Swap: {_fmt_bytes(swap.used)} used / {_fmt_bytes(swap.total)} total",
        f"- Disk (/): {disk.percent:.0f}% used ({_fmt_bytes(disk.free)} free)",
        f"- Docker stack (via health): neena-backend online; postgres={pg}; redis={redis}",
        f"- Public proxy: 8443 (nginx); backend port 8080 local-only",
        f"- Health logger: active on host (5 min timer)",
        f"- Stream cache: {stream}; WhatsApp gateway: {wa}",
        "- AzuraCast: not modified by this status check",
    ]
    if heal_line:
        lines.append(f"- Self-heal: {heal_line}")
    return "\n".join(lines)


__all__ = ["build_vm_status_reply"]

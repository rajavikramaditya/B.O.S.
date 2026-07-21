"""Proactive VM resource monitor + emergency self-heal escalate.

Sole periodic distress loop: sustained CPU/RAM/disk → owner alert, then
allowlisted heal ladder (WhatsApp gateway → neena-backend → host reboot).
One-second CPU blips are ignored.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

import psutil
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db
from services.cockpit.runtime_controller import get_whatsapp_gateway_url
from services.safety.security_config import get_ssl_verify

logger = logging.getLogger(__name__)

CPU_THRESHOLD = float(os.environ.get("RESMON_CPU_THRESHOLD", "90"))
RAM_THRESHOLD = float(os.environ.get("RESMON_RAM_THRESHOLD", "88"))
DISK_THRESHOLD = float(os.environ.get("RESMON_DISK_THRESHOLD", "85"))
CPU_CRITICAL = float(os.environ.get("RESMON_CPU_CRITICAL", "95"))
CPU_SUSTAINED_CYCLES = int(os.environ.get("RESMON_CPU_SUSTAINED_CYCLES", "3"))
CPU_SAMPLES = int(os.environ.get("RESMON_CPU_SAMPLES", "3"))
CHECK_INTERVAL_SECONDS = int(os.environ.get("RESMON_INTERVAL_SECONDS", "120"))
COOLDOWN_PERIOD_SECONDS = int(os.environ.get("RESMON_COOLDOWN_SECONDS", "3600"))
# Extra sustained cycles after warn before soft heal / next escalate step.
HEAL_SOFT_EXTRA = int(os.environ.get("RESMON_HEAL_SOFT_EXTRA", "2"))
HEAL_BACKEND_EXTRA = int(os.environ.get("RESMON_HEAL_BACKEND_EXTRA", "2"))
HEAL_REBOOT_EXTRA = int(os.environ.get("RESMON_HEAL_REBOOT_EXTRA", "3"))

last_warning_sent_time = 0.0
_cpu_high_streak = 0
_gateway_error_logged_at = 0.0
_heal_stage = 0  # 0 none, 1 soft done, 2 backend done, 3 reboot requested


def _sample_cpu_avg() -> float:
    readings = []
    for _ in range(max(1, CPU_SAMPLES)):
        readings.append(psutil.cpu_percent(interval=1.0))
    return round(sum(readings) / len(readings), 1)


def _explain(metric: str, value: float, threshold: float, sustained_min: float) -> str:
    if metric == "cpu":
        return (
            f"CPU load ~{value}% (limit {threshold:.0f}%) aur ye pichhle "
            f"~{sustained_min:.0f} min se lagataar high hai. Matlab processing ka "
            f"kaam zyada aa raha hai — dashboard/voice thoda slow ho sakta hai."
        )
    if metric == "ram":
        return (
            f"RAM usage {value}% (limit {threshold:.0f}%). Memory bhar rahi hai — "
            f"agar aur badhi to backend restart/crash ho sakta hai."
        )
    return (
        f"Disk {value}% bhar chuki hai (limit {threshold:.0f}%). Nayi recordings/"
        f"logs rukne ka risk hai."
    )


def _build_owner_message(problems, healthy_note, heal_note: str = "") -> str:
    lines = ["Neena Gupta yahan, Sir. Server par ek cheez dhyaan dene layak hai:"]
    for p in problems:
        lines.append(f"\n• {p['reason']}")
    if healthy_note:
        lines.append(f"\nBaaki theek hai: {healthy_note}.")
    if heal_note:
        lines.append(f"\nSelf-heal: {heal_note}")
    else:
        lines.append("\nAbhi kya karein: " + problems[0]["action"])
    return "".join(lines)


def _send_owner_whatsapp(message: str) -> bool:
    owner_raw = os.environ.get("OWNER_WHATSAPP_NUMBER", "").strip()
    owner_digits = "".join(c for c in owner_raw if c.isdigit())
    if not owner_digits:
        logger.info("[ResourceMonitor] OWNER_WHATSAPP_NUMBER not set; skipping push.")
        return False
    gateway_url = get_whatsapp_gateway_url("send-message")
    try:
        res = requests.post(
            gateway_url,
            json={"phone": owner_digits, "message": message},
            timeout=5.0,
            verify=get_ssl_verify(),
        )
        return res.status_code == 200
    except Exception as exc:  # noqa: BLE001
        global _gateway_error_logged_at
        now = time.time()
        if now - _gateway_error_logged_at > 300:
            logger.error("[ResourceMonitor] Gateway push failed: %s", exc)
            _gateway_error_logged_at = now
        return False


def _maybe_escalate_heal(cpu: float, ram: float, disk: float, cpu_sustained: bool) -> str:
    """Run allowlisted heal ladder when CPU stays critical. Returns note for owner."""
    global _heal_stage

    from services.cockpit import self_heal

    if not self_heal.self_heal_enabled():
        return ""
    if not cpu_sustained or cpu < CPU_CRITICAL:
        if _cpu_high_streak == 0 and _heal_stage:
            _heal_stage = 0
            self_heal.reset_incident_steps()
        return ""

    metrics = {"cpu": cpu, "ram": ram, "disk": disk, "streak": _cpu_high_streak}
    reason = f"sustained CPU {cpu}% streak={_cpu_high_streak}"
    base = CPU_SUSTAINED_CYCLES

    # Soft: WhatsApp/Chrome restart
    if _heal_stage < 1 and _cpu_high_streak >= base + HEAL_SOFT_EXTRA:
        res = self_heal.request_heal("gateway_restart", reason=reason, metrics=metrics)
        if res.get("ok"):
            _heal_stage = 1
            return (
                "WhatsApp gateway restart request bhej di (Chrome load kam karne ke liye)."
                + (" [dry-run]" if res.get("dry_run") else "")
            )
        return f"Soft heal skip: {res.get('error')}"

    # Backend restart
    if _heal_stage == 1 and _cpu_high_streak >= base + HEAL_SOFT_EXTRA + HEAL_BACKEND_EXTRA:
        res = self_heal.request_heal("backend_restart", reason=reason, metrics=metrics)
        if res.get("ok"):
            _heal_stage = 2
            return (
                "neena-backend restart request bhej di."
                + (" [dry-run]" if res.get("dry_run") else "")
            )
        return f"Backend heal skip: {res.get('error')}"

    # Host reboot last resort
    if _heal_stage == 2 and _cpu_high_streak >= (
        base + HEAL_SOFT_EXTRA + HEAL_BACKEND_EXTRA + HEAL_REBOOT_EXTRA
    ):
        res = self_heal.request_heal("host_reboot", reason=reason, metrics=metrics)
        if res.get("ok"):
            _heal_stage = 3
            return (
                "Host reboot request bhej di — online aate hi report karungi."
                + (" [dry-run]" if res.get("dry_run") else "")
            )
        return f"Reboot skip: {res.get('error')}"

    if _heal_stage >= 1:
        return f"Heal armed (stage {_heal_stage}); abhi escalate wait."
    return "Heal armed — agar load na gire to soft restart khud try karungi."


async def check_and_alert_resources():
    global last_warning_sent_time, _cpu_high_streak

    cpu = _sample_cpu_avg()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    if cpu > CPU_THRESHOLD:
        _cpu_high_streak += 1
    else:
        _cpu_high_streak = 0
    cpu_sustained = _cpu_high_streak >= CPU_SUSTAINED_CYCLES
    sustained_min = (CPU_SUSTAINED_CYCLES * CHECK_INTERVAL_SECONDS) / 60.0

    heal_note = _maybe_escalate_heal(cpu, ram, disk, cpu_sustained)

    problems = []
    if cpu_sustained:
        problems.append({
            "reason": _explain("cpu", cpu, CPU_THRESHOLD, sustained_min),
            "action": (
                "Self-heal ladder chal rahi hai (gateway → backend → reboot). "
                "Agar baar-baar ho to capacity alag se socho."
            ),
        })
    if ram > RAM_THRESHOLD:
        problems.append({
            "reason": _explain("ram", ram, RAM_THRESHOLD, 0),
            "action": "Backend memory check / neena-backend restart.",
        })
    if disk > DISK_THRESHOLD:
        problems.append({
            "reason": _explain("disk", disk, DISK_THRESHOLD, 0),
            "action": "Purani recordings/logs clean ya disk badhao.",
        })

    # Heal-only notify when we actually requested a step (even if alert cooldown).
    if heal_note and ("request bhej" in heal_note or "DRY" in heal_note.upper() or "dry-run" in heal_note):
        _send_owner_whatsapp(
            f"Neena Gupta: self-heal step — {heal_note} "
            f"(CPU {cpu}% RAM {ram}% Disk {disk}% streak {_cpu_high_streak})."
        )
        try:
            db.add_activity_log("system", f"Self-heal: {heal_note}")
        except Exception:
            pass

    if not problems:
        return

    now = time.time()
    if now - last_warning_sent_time <= COOLDOWN_PERIOD_SECONDS:
        return

    healthy_bits = []
    if not cpu_sustained:
        healthy_bits.append(f"CPU {cpu}%")
    if ram <= RAM_THRESHOLD:
        healthy_bits.append(f"RAM {ram}%")
    if disk <= DISK_THRESHOLD:
        healthy_bits.append(f"Disk {disk}%")
    healthy_note = ", ".join(healthy_bits)

    message = _build_owner_message(problems, healthy_note, heal_note=heal_note)
    logger.warning(
        "[ResourceMonitor] Real issue: cpu=%s%%(streak %s) ram=%s%% disk=%s%% heal=%s",
        cpu, _cpu_high_streak, ram, disk, heal_note or "-",
    )
    if _send_owner_whatsapp(message):
        last_warning_sent_time = now
        logger.info("[ResourceMonitor] Owner alert sent.")
        db.add_activity_log(
            "system",
            f"Resource alert sent: cpu={cpu}% ram={ram}% disk={disk}% (cpu_sustained={cpu_sustained})",
        )


async def start_monitoring_loop():
    logger.info("[ResourceMonitor] Proactive System Resource Daemon started successfully.")
    await asyncio.sleep(15)
    while True:
        try:
            await check_and_alert_resources()
        except Exception as e:  # noqa: BLE001
            logger.error("[ResourceMonitor] Error in monitoring loop: %s", e)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

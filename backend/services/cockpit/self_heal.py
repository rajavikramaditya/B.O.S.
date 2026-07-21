"""Owner-preauthorized emergency self-heal (allowlisted host actions only).

resource_monitor is the sole caller. Python never runs freeform shell —
it writes a request JSON for the host agent (neena-self-heal.sh).

Allowlist: gateway_restart | backend_restart | host_reboot.
Never AzuraCast / Postgres / Redis.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = frozenset({"gateway_restart", "backend_restart", "host_reboot"})

# Shared with host agent (compose mounts /var/lib/neena).
_DEFAULT_DIR = "/var/lib/neena"
_REQUEST_NAME = "self_heal_request.json"
_PENDING_NAME = "self_heal_pending.json"
_LAST_NAME = "self_heal_last.json"
_STATE_NAME = "self_heal_state.json"


def _state_dir() -> Path:
    return Path(os.environ.get("NEENA_SELF_HEAL_DIR", _DEFAULT_DIR))


def self_heal_enabled() -> bool:
    from services.brain.feature_flags import self_heal_enabled as _flag

    return _flag()


def self_heal_reboot_allowed() -> bool:
    from services.brain.feature_flags import self_heal_reboot_allowed as _flag

    return _flag()


def self_heal_dry_run() -> bool:
    from services.brain.feature_flags import self_heal_dry_run as _flag

    return _flag()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_state() -> dict[str, Any]:
    return _read_json(_state_dir() / _STATE_NAME) or {}


def _save_state(state: dict[str, Any]) -> None:
    _write_json(_state_dir() / _STATE_NAME, state)


def last_heal_summary_line() -> str | None:
    last = _read_json(_state_dir() / _LAST_NAME)
    if not last:
        return None
    action = last.get("action") or "?"
    ok = last.get("ok")
    ts = last.get("ts") or "?"
    return f"{action} ok={ok} at {ts}"


def load_pending_announce() -> dict[str, Any] | None:
    return _read_json(_state_dir() / _PENDING_NAME)


def clear_pending_announce() -> None:
    path = _state_dir() / _PENDING_NAME
    try:
        if path.is_file():
            path.unlink()
    except Exception as exc:
        logger.warning("[self_heal] clear pending failed: %s", exc)


def write_pending_announce(payload: dict[str, Any]) -> None:
    _write_json(_state_dir() / _PENDING_NAME, payload)


def cooldown_ok(action: str, *, now: float | None = None) -> bool:
    """Per-action + host_reboot global cooldowns."""
    now = now if now is not None else time.time()
    state = _load_state()
    soft_cd = float(os.environ.get("NEENA_SELF_HEAL_SOFT_COOLDOWN_SEC", "1800"))
    reboot_cd = float(os.environ.get("NEENA_SELF_HEAL_REBOOT_COOLDOWN_SEC", "21600"))
    last_by = state.get("last_by_action") or {}
    last_ts = float(last_by.get(action) or 0)
    cd = reboot_cd if action == "host_reboot" else soft_cd
    if last_ts and (now - last_ts) < cd:
        return False
    return True


def mark_action_attempted(action: str, *, ok: bool, detail: str = "") -> None:
    now = time.time()
    state = _load_state()
    last_by = dict(state.get("last_by_action") or {})
    last_by[action] = now
    steps = list(state.get("steps_this_incident") or [])
    steps.append({"action": action, "ok": ok, "ts": now, "detail": detail[:200]})
    state["last_by_action"] = last_by
    state["steps_this_incident"] = steps[-12:]
    state["updated_at"] = now
    _save_state(state)
    _write_json(
        _state_dir() / _LAST_NAME,
        {"action": action, "ok": ok, "ts": now, "detail": detail[:200]},
    )


def reset_incident_steps() -> None:
    state = _load_state()
    state["steps_this_incident"] = []
    _save_state(state)


def incident_steps() -> list[dict[str, Any]]:
    return list((_load_state().get("steps_this_incident") or []))


def request_heal(
    action: str,
    *,
    reason: str,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue an allowlisted heal for the host agent. Never freeform shell."""
    action = (action or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        return {"ok": False, "error": "action_not_allowlisted", "action": action}
    if not self_heal_enabled():
        return {"ok": False, "error": "self_heal_disabled", "action": action}
    if action == "host_reboot" and not self_heal_reboot_allowed():
        return {"ok": False, "error": "reboot_not_allowed", "action": action}
    if not cooldown_ok(action):
        return {"ok": False, "error": "cooldown", "action": action}

    metrics = dict(metrics or {})
    payload = {
        "action": action,
        "reason": (reason or "")[:400],
        "metrics": metrics,
        "ts": time.time(),
        "requested_by": "resource_monitor",
    }

    if self_heal_dry_run():
        logger.warning("[self_heal] DRY_RUN would request %s: %s", action, payload)
        mark_action_attempted(action, ok=True, detail="dry_run")
        return {"ok": True, "dry_run": True, "action": action, "payload": payload}

    # Pending announce before reboot so boot can report even if request is consumed.
    if action == "host_reboot":
        write_pending_announce(
            {
                "reason": reason,
                "metrics": metrics,
                "steps_tried": incident_steps(),
                "action": action,
                "ts": time.time(),
            }
        )

    req_path = _state_dir() / _REQUEST_NAME
    try:
        _write_json(req_path, payload)
    except Exception as exc:
        logger.error("[self_heal] write request failed: %s", exc)
        return {"ok": False, "error": "write_failed", "detail": str(exc)[:200]}

    mark_action_attempted(action, ok=True, detail="request_written")
    logger.warning("[self_heal] requested %s → %s", action, req_path)
    return {"ok": True, "action": action, "path": str(req_path)}


def announce_pending_on_boot() -> bool:
    """If a pending self-heal flag exists, WhatsApp the owner once and clear it."""
    pending = load_pending_announce()
    if not pending:
        return False
    try:
        from services.brain.owner_notifier import notify_owner
        import psutil

        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory().percent
        steps = pending.get("steps_tried") or []
        step_txt = ", ".join(
            f"{s.get('action')}({'ok' if s.get('ok') else 'fail'})" for s in steps
        ) or "none"
        reason = pending.get("reason") or "critical load"
        msg = (
            "Neena Gupta yahan, Sir. System critical tha isliye maine self-heal chalaya "
            f"({pending.get('action') or 'heal'}). Reason: {reason}. "
            f"Steps: {step_txt}. Ab online hoon — CPU abhi ~{cpu:.0f}%, RAM ~{ram:.0f}%."
        )
        notify_owner(msg)
        try:
            import database as db

            db.add_activity_log("system", f"Self-heal boot announce: {pending.get('action')}")
        except Exception:
            pass
    except Exception as exc:
        logger.error("[self_heal] boot announce failed: %s", exc)
        return False
    finally:
        clear_pending_announce()
    return True


__all__ = [
    "ALLOWED_ACTIONS",
    "announce_pending_on_boot",
    "clear_pending_announce",
    "cooldown_ok",
    "incident_steps",
    "last_heal_summary_line",
    "load_pending_announce",
    "mark_action_attempted",
    "request_heal",
    "reset_incident_steps",
    "self_heal_dry_run",
    "self_heal_enabled",
    "self_heal_reboot_allowed",
    "write_pending_announce",
]

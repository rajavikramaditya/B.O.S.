#!/usr/bin/env python3
"""M4-A7 launch hardening rehearsal — READY / PARTIAL / BLOCKED / FAILED."""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND = os.path.join(ROOT, "frontend")
API = os.environ.get("ORAI_API_BASE", "http://127.0.0.1:8000/api")
BASE = API.rsplit("/api", 1)[0]
FAST_TIMEOUT = 12.0
DEEP_TIMEOUT = 20.0

SECRET_PATTERNS = (
    r'"gemini_api_key"\s*:\s*"[A-Za-z0-9_\-]{8,}"',
    r'"elevenlabs_api_key"\s*:\s*"[A-Za-z0-9_\-]{8,}"',
    r'"azuracast_api_key"\s*:\s*"[A-Za-z0-9_\-]{8,}"',
    r'"admin_api_key"\s*:\s*"[A-Za-z0-9_\-]{8,}"',
    r"AIza[0-9A-Za-z_\-]{20,}",
    r"sk_[A-Za-z0-9]{20,}",
)


def _leaks_secrets(payload: str) -> list[str]:
    hits = []
    for pat in SECRET_PATTERNS:
        if re.search(pat, payload, re.IGNORECASE):
            hits.append(pat)
    return hits


def main() -> int:
    notes: list[str] = []
    blockers: list[str] = []
    failures: list[str] = []

    # Static assets
    for rel in ("index.html", "app.js", "style.css"):
        path = os.path.join(FRONTEND, rel)
        if not os.path.exists(path):
            failures.append(f"static missing: {rel}")
        elif "cockpit-layout" in open(path, encoding="utf-8").read() and rel == "index.html":
            notes.append("Command Center static present")

    backend_up = False
    try:
        r = requests.get(f"{BASE}/api/neena/cockpit-status", timeout=FAST_TIMEOUT)
        backend_up = r.status_code == 200
        if backend_up:
            elapsed = r.elapsed.total_seconds()
            data = r.json()
            notes.append(f"cockpit-status 200 in {elapsed:.2f}s tier={data.get('health_tier')}")
            if elapsed > 8.0:
                blockers.append("cockpit-status slower than 8s on cold start")
            leaks = _leaks_secrets(json.dumps(data))
            if leaks:
                failures.append(f"secrets leaked in cockpit-status patterns={leaks}")
            if not data.get("broadcast_readiness"):
                blockers.append("broadcast_readiness missing in cockpit-status")
            verified = data.get("last_verified_capsule_id")
            if not verified:
                try:
                    caps = requests.get(f"{API}/broadcast/capsules?limit=50", timeout=8).json()
                    for c in caps.get("capsules") or []:
                        if c.get("stream_verification_status") == "verified":
                            verified = c.get("id")
                            break
                except Exception:
                    pass
            if verified:
                notes.append(f"last verified capsule #{verified}")
            else:
                blockers.append("no verified capsule in recent list")
            tts = (data.get("broadcast_readiness") or {}).get("audio", {})
            if tts.get("tts_status") == "real_available" or tts.get("can_produce_real_audio"):
                notes.append("Gemini TTS readiness: real path available")
            else:
                blockers.append("Gemini TTS not marked real_available")
            az = (data.get("broadcast_readiness") or {}).get("azuracast", {})
            if az.get("ready_for_real_push"):
                notes.append("AzuraCast write config ready")
            else:
                blockers.append("AzuraCast write config not ready")
            if data.get("stream_online"):
                notes.append("stream online")
            else:
                blockers.append("stream offline or uncached")
        else:
            failures.append(f"cockpit-status HTTP {r.status_code}")
    except requests.RequestException as exc:
        failures.append(f"backend unreachable: {exc}")

    if backend_up:
        try:
            t0 = time.time()
            r = requests.get(f"{BASE}/api/neena/launch-health", timeout=DEEP_TIMEOUT)
            dt = time.time() - t0
            if r.status_code == 200:
                d = r.json()
                notes.append(
                    f"launch-health 200 in {dt:.2f}s tier={d.get('health_tier')} cached={d.get('cached')}"
                )
                if d.get("health_tier") != "deep_health":
                    blockers.append("launch-health missing deep_health label (restart backend on new code)")
                if d.get("degraded_due_to_memory_stack_offline"):
                    blockers.append("memory stack offline (deep health degraded)")
                leaks = _leaks_secrets(json.dumps(d))
                if leaks:
                    failures.append(f"secrets leaked in launch-health patterns={leaks}")
            else:
                blockers.append(f"launch-health HTTP {r.status_code}")
        except requests.RequestException as exc:
            blockers.append(f"launch-health timeout/error: {exc}")

        try:
            sec = requests.get(f"{BASE}/api/neena/security-status", timeout=5).json()
            exposure = (sec.get("security") or {}).get("exposure_mode")
            notes.append(f"security exposure_mode={exposure}")
            if exposure == "network_exposed_auth_missing":
                blockers.append(sec["security"].get("launch_blocker") or "admin auth missing")
        except Exception:
            blockers.append("security-status unavailable")

    host = BASE.replace("http://", "").replace("https://", "").split("/")[0]
    if not host.startswith("127.0.0.1") and not host.startswith("localhost"):
        blockers.append("DANGEROUS: API base is not localhost — admin console may be publicly exposed")

    # Memory stack (optional)
    try:
        import subprocess

        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scratch", "check_memory_stack.py")],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=ROOT,
        )
        if proc.returncode == 0:
            notes.append("memory stack healthy")
        else:
            blockers.append("memory stack not healthy (Docker/Postgres/Redis)")
    except Exception as exc:
        blockers.append(f"memory stack check skipped: {type(exc).__name__}")

    if failures:
        verdict = "FAILED"
    elif blockers:
        verdict = "BLOCKED" if not backend_up else "PARTIAL"
    elif backend_up:
        verdict = "READY"
    else:
        verdict = "FAILED"

    print("M4-A7 Launch Hardening Rehearsal")
    print(f"VERDICT: {verdict}")
    for n in notes:
        print(f"  note: {n}")
    for b in blockers:
        print(f"  blocker: {b}")
    for f in failures:
        print(f"  fail: {f}")

    if verdict == "READY":
        return 0
    if verdict == "PARTIAL":
        return 2
    if verdict == "BLOCKED":
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

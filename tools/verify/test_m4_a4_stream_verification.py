#!/usr/bin/env python3
"""M4-A4 stream verification smoke — uses capsule #23 if uploaded."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
ENV_PATH = os.path.join(ROOT, ".env")
sys.path.insert(0, BACKEND)


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")


_load_env()

import database as db
from services.broadcast.capsule_service import get_capsule_by_id
from services.broadcast.stream_verification import verify_capsule_stream_status

TARGET_CAPSULE_ID = 23


def main() -> int:
    db.init_db()
    failures: list[str] = []

    bad = verify_capsule_stream_status(999999)
    if not bad.get("blocked") and bad.get("success"):
        failures.append("C: missing capsule should not succeed")

    pending = None
    for cid in range(1, 50):
        cap = get_capsule_by_id(cid)
        if cap and cap.get("azuracast_status") not in ("uploaded", "scheduled"):
            pending = cap
            break
    if pending:
        gate = verify_capsule_stream_status(pending["id"])
        if not gate.get("blocked"):
            failures.append("D: non-uploaded capsule should be blocked")

    cap = get_capsule_by_id(TARGET_CAPSULE_ID)
    if not cap:
        print(f"M4-A4 smoke SKIP: capsule #{TARGET_CAPSULE_ID} not found")
        return 0

    if cap.get("azuracast_status") not in ("uploaded", "scheduled"):
        print(f"M4-A4 smoke SKIP: capsule #{TARGET_CAPSULE_ID} status={cap.get('azuracast_status')}")
        return 0

    result = verify_capsule_stream_status(TARGET_CAPSULE_ID, watch_seconds=0)
    print(f"A: capsule #{TARGET_CAPSULE_ID} verification_status={result.get('verification_status')}")
    print(f"   stream_reachable={result.get('stream_reachable')} now_playing_match={result.get('now_playing_match')}")
    print(f"   message={result.get('message')}")

    if result.get("verification_status") == "verified" and not result.get("now_playing_match"):
        failures.append("A: cannot mark verified without now_playing_match")

    if result.get("stream_verification_status") == "verified" and result.get("verification_status") != "verified":
        failures.append("A: DB verified only when verification_status verified")

    # Quick watch test capped at 15s for smoke (not full 60)
    watch = verify_capsule_stream_status(TARGET_CAPSULE_ID, watch_seconds=15)
    print(f"B: watch verification_status={watch.get('verification_status')} polls={watch.get('watch_polls', 0)}")

    if failures:
        print("M4-A4 smoke FAILED:")
        for f in failures:
            print(" -", f)
        return 1

    print("M4-A4 smoke PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

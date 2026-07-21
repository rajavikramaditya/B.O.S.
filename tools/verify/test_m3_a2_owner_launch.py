#!/usr/bin/env python3
"""M3-A2 owner launch tests through backend :8000."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/neena/chat"
HEALTH = "http://127.0.0.1:8000/api/neena/launch-health"
TIMEOUT = 120


def post_chat(message: str) -> dict:
    body = json.dumps({"message": message, "model": "auto"}).encode("utf-8")
    req = urllib.request.Request(
        BASE,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_launch_health() -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"launch-health HTTP {exc.code}")
        return None


def main() -> int:
    results: list[str] = []
    failed = 0

    health = get_launch_health()
    if health:
        results.append(f"launch-health OK: {health}")
    else:
        results.append("launch-health missing (backend restart may be needed)")

    tests = [
        ("A status", "Neena status batao", lambda r: "station" in (r.get("route") or "") or "status" in (r.get("reply") or "").lower()),
        ("B diagnostics", "diagnostics run karo", lambda r: "diagnostic" in (r.get("route") or "").lower() or "diagnostic" in (r.get("reply") or "").lower()),
        ("C rj intro", "kal subah ke show ke liye Orai touch ke sath funny RJ intro banao", lambda r: bool(r.get("reply")) and r.get("route") not in ("blocked_creative", "blocked")),
        ("D ad script (rapid)", "Mahil Kingdom ke liye 20 second ka radio ad script banao", lambda r: bool(r.get("reply"))),
        ("E memory read", "meri RJ script tone preference kya hai?", lambda r: bool(r.get("reply"))),
    ]

    prev = None
    for label, msg, check in tests:
        try:
            if label.startswith("D") and prev:
                time.sleep(0.3)
            data = post_chat(msg)
            ok = check(data)
            route = data.get("route")
            rate = data.get("model_rate_limited")
            reply_snip = (data.get("reply") or "")[:120].replace("\n", " ")
            results.append(
                f"{label}: {'PASS' if ok else 'FAIL'} route={route} rate_limited={rate} reply={reply_snip!r}"
            )
            if not ok:
                failed += 1
            if label == "C rj intro":
                prev = data
        except Exception as exc:
            results.append(f"{label}: ERROR {exc}")
            failed += 1

    # F memory save + approval
    try:
        save = post_chat(
            "Neena ke ad script me offer line simple rakha karo, is baat ko permanent memory me save karo"
        )
        pending = save.get("pending_approval_active") or save.get("pending_candidate_active")
        results.append(
            f"F save: route={save.get('route')} pending={pending} memory_save={save.get('memory_save_status')}"
        )
        appr = post_chat("approved")
        pg = appr.get("postgres_write_status")
        sqlite = appr.get("sqlite_mirror_status")
        results.append(
            f"F approved: route={appr.get('route')} pg={pg} sqlite={sqlite} approval={appr.get('approval_consumed')}"
        )
        if appr.get("approval_consumed") != "Yes" and "save" not in (appr.get("reply") or "").lower():
            failed += 1
            results.append("F approved: FAIL approval path")
        else:
            results.append("F approved: PASS")
    except Exception as exc:
        results.append(f"F: ERROR {exc}")
        failed += 1

    print("\n".join(results))
    print(f"\nSummary: {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

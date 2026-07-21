#!/usr/bin/env python3
"""Neena interaction probe — agent self-tests like a real owner, then analyzes.

Modes:
  run      Send owner-like turns (in-process brain OR HTTP API).
  analyze  Read command-center recorder / a probe JSON report and flag bugs.
  probe    run + analyze in one pass (default for agent workflow).

Safety:
  - Never prints/stores unlock phrases, API keys, or .env secrets.
  - Default scenario pack is smoke-only (no broadcast / real TTS / delete).
  - HTTP mode needs an already-unlocked session cookie file if hitting /api/neena/chat.

Examples:
  python scripts/neena_interaction_probe.py probe --mode inprocess
  python scripts/neena_interaction_probe.py analyze --limit 30
  python scripts/neena_interaction_probe.py run --mode http --base-url http://127.0.0.1:8080 \\
      --cookie-file runtime/tmp/vm_cookie.txt --scenario owner_smoke
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCENARIO_DIR = Path(__file__).resolve().parent / "interaction_scenarios"
DEFAULT_OUT_DIR = ROOT / "runtime" / "probes"

# Heuristics for unexpected / buggy owner experience (Hinglish + English).
_ROBOTIC_MARKERS = (
    "cpu:",
    "ram:",
    "disk:",
    "vm status",
    "model status",
    "memory stack",
    "redis:",
    "postgres:",
    "latency_ms",
    "• ",
    "- cpu",
    "- ram",
)
_FALSE_CLAIM_MARKERS = (
    "save kar diya",
    "save kar liya",
    "yaad rakh liya",
    "permanent memory me save",
    "broadcast kar diya",
    "air pe bhej diya",
    "upload ho gaya",
)
_CONFUSION_MARKERS = (
    "samajh nahi aaya",
    "clarify",
    "kaunsa command",
    "please rephrase",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_backend_path() -> None:
    backend = str(BACKEND)
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _load_scenario(name: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Scenario not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _clip(text: str | None, n: int = 240) -> str:
    value = (text or "").strip().replace("\n", " ")
    return value if len(value) <= n else value[: n - 3] + "..."


def _send_inprocess(message: str, model: str = "auto") -> dict[str, Any]:
    _ensure_backend_path()
    from services.brain.brain import process_owner_message
    from services.cockpit.recorder import record_probe_turn

    started = time.monotonic()
    result = process_owner_message(message, selected_model=model) or {}
    latency_ms = round((time.monotonic() - started) * 1000)
    result = dict(result)
    result["_probe_latency_ms"] = latency_ms
    result["_probe_transport"] = "inprocess"
    try:
        record_probe_turn(user_input=message, result=result, latency_ms=latency_ms)
    except Exception:
        pass
    return result


def _send_http(
    message: str,
    *,
    base_url: str,
    cookie_file: str | None,
    model: str = "auto",
    timeout: float = 90.0,
) -> dict[str, Any]:
    import requests

    url = base_url.rstrip("/") + "/api/neena/chat"
    headers = {"Content-Type": "application/json"}
    cookies = {}
    if cookie_file and Path(cookie_file).is_file():
        # Netscape-ish or simple "name=value" lines; never log cookie values.
        for line in Path(cookie_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
            elif "=" in line:
                k, v = line.split("=", 1)
                cookies[k.strip()] = v.strip()

    started = time.monotonic()
    res = requests.post(
        url,
        json={"message": message, "model": model},
        headers=headers,
        cookies=cookies or None,
        timeout=timeout,
    )
    latency_ms = round((time.monotonic() - started) * 1000)
    try:
        body = res.json()
    except Exception:
        body = {"reply": res.text, "detail": f"non_json_http_{res.status_code}"}
    if not isinstance(body, dict):
        body = {"reply": str(body)}
    body["_probe_latency_ms"] = latency_ms
    body["_probe_transport"] = "http"
    body["_probe_http_status"] = res.status_code
    return body


def _turn_flags(turn: dict[str, Any], expect: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return list of {severity, code, detail} findings for one turn."""
    expect = expect or {}
    findings: list[dict[str, str]] = []
    reply = (turn.get("assistant_reply") or turn.get("reply") or "").strip()
    reply_l = reply.lower()
    latency = turn.get("latency_ms")
    if latency is None:
        latency = turn.get("_probe_latency_ms")
    action = (turn.get("action_type") or turn.get("action") or "").strip()
    intent = (turn.get("intent") or "").strip()
    route = (turn.get("route") or "").strip()
    http_status = turn.get("_probe_http_status")

    if http_status and int(http_status) >= 400:
        findings.append(
            {
                "severity": "high",
                "code": "http_error",
                "detail": f"HTTP {http_status}: {_clip(reply or turn.get('detail'), 120)}",
            }
        )

    if expect.get("reply_not_empty", True) and not reply:
        findings.append({"severity": "high", "code": "empty_reply", "detail": "No assistant reply"})

    max_lat = expect.get("max_latency_ms")
    if max_lat is not None and latency is not None and int(latency) > int(max_lat):
        findings.append(
            {
                "severity": "medium",
                "code": "slow_reply",
                "detail": f"latency {latency}ms > budget {max_lat}ms",
            }
        )
    elif latency is not None and int(latency) >= 40000:
        findings.append(
            {
                "severity": "high",
                "code": "very_slow_reply",
                "detail": f"latency {latency}ms (>=40s) — timeout-fallback may have failed",
            }
        )

    for bad in expect.get("forbid_substrings") or []:
        if bad.lower() in reply_l:
            findings.append(
                {
                    "severity": "medium",
                    "code": "forbidden_substring",
                    "detail": f"reply contains {bad!r}",
                }
            )

    prefer = [a.lower() for a in (expect.get("prefer_actions") or [])]
    if prefer:
        hay = f"{action} {intent} {route}".lower()
        if not any(p in hay for p in prefer):
            findings.append(
                {
                    "severity": "medium",
                    "code": "unexpected_action",
                    "detail": f"got action/intent/route={action!r}/{intent!r}/{route!r}; preferred {prefer}",
                }
            )

    forbid_actions = [a.lower() for a in (expect.get("forbid_actions") or [])]
    if forbid_actions:
        hay = f"{action} {intent} {route}".lower()
        hit = [a for a in forbid_actions if a in hay]
        if hit:
            findings.append(
                {
                    "severity": "high",
                    "code": "dangerous_action",
                    "detail": f"forbidden action matched: {hit}",
                }
            )

    # Robotic template dump heuristic (status-like bullets without human phrasing).
    robotic_hits = [m for m in _ROBOTIC_MARKERS if m in reply_l]
    if len(robotic_hits) >= 3 and len(reply) > 180:
        findings.append(
            {
                "severity": "low",
                "code": "robotic_dump",
                "detail": f"reply looks like template dump ({', '.join(robotic_hits[:4])})",
            }
        )

    for claim in _FALSE_CLAIM_MARKERS:
        if claim in reply_l and "nahi" not in reply_l and "pending" not in reply_l:
            # Soft signal — agent must verify against trace before treating as bug.
            findings.append(
                {
                    "severity": "low",
                    "code": "possible_false_claim",
                    "detail": f"reply may claim irreversible success: {claim!r}",
                }
            )

    if any(m in reply_l for m in _CONFUSION_MARKERS) and len((turn.get("user_input") or "").split()) <= 8:
        findings.append(
            {
                "severity": "low",
                "code": "over_clarify",
                "detail": "short owner message got a clarify/confused reply",
            }
        )

    trace = turn.get("trace") if isinstance(turn.get("trace"), dict) else {}
    if turn.get("pending_cleared_without_execute") or trace.get("pending_cleared_without_execute"):
        findings.append(
            {
                "severity": "medium",
                "code": "pending_cleared_without_execute",
                "detail": "protected pending was cleared without executing (owner may have meant confirm)",
            }
        )
    reached = turn.get("reached_interpreter")
    if reached is None:
        reached = trace.get("reached_interpreter")
    short = turn.get("short_circuit_reason") or trace.get("short_circuit_reason")
    action_l = (turn.get("action_type") or "").lower()
    if (
        reached is False
        and short
        and short not in (
            "one_tap_confirm_accepted",
            "one_tap_cancelled",
            "permanent_memory_confirm",
            "confirm_without_pending",
        )
        and "confirm" in action_l
    ):
        findings.append(
            {
                "severity": "medium",
                "code": "never_reached_interpreter",
                "detail": f"turn short-circuited before interpreter ({short})",
            }
        )
    if (turn.get("action_type") or "") == "SEND_AZURACAST_CONFIRM":
        # Repeated confirm theatre often means affirmatives were not accepted.
        findings.append(
            {
                "severity": "low",
                "code": "confirm_loop_signal",
                "detail": "SEND_AZURACAST_CONFIRM — check if prior turn cleared pending without execute",
            }
        )

    return findings


def run_scenario(
    scenario: dict[str, Any],
    *,
    transport: str,
    base_url: str | None,
    cookie_file: str | None,
    model: str,
    pause_s: float,
) -> dict[str, Any]:
    turns_out: list[dict[str, Any]] = []
    for spec in scenario.get("turns") or []:
        msg = (spec.get("message") or "").strip()
        if not msg:
            continue
        if transport == "http":
            if not base_url:
                raise ValueError("--base-url required for http mode")
            result = _send_http(msg, base_url=base_url, cookie_file=cookie_file, model=model)
        else:
            result = _send_inprocess(msg, model=model)

        turn = {
            "id": spec.get("id") or f"t{len(turns_out)+1}",
            "user_input": msg,
            "assistant_reply": result.get("reply") or result.get("message") or "",
            "action_type": result.get("action_type"),
            "intent": result.get("intent") or result.get("operation_intent"),
            "route": result.get("route"),
            "policy_decision": result.get("policy_decision"),
            "actual_model": result.get("actual_model") or result.get("actual_api_model_id"),
            "latency_ms": result.get("_probe_latency_ms"),
            "require_confirmation": result.get("require_confirmation"),
            "trace_keys": sorted(
                k
                for k in (
                    "source",
                    "route",
                    "final_reply_source",
                    "fallback_used",
                    "fallback_model_used",
                    "model_call_status",
                    "session_backend",
                )
                if result.get(k) is not None
            ),
            "selected_fields": {
                k: result.get(k)
                for k in (
                    "source",
                    "route",
                    "final_reply_source",
                    "fallback_used",
                    "fallback_model_used",
                    "model_call_status",
                    "session_backend",
                    "llm_provider",
                    "llm_status",
                )
                if result.get(k) is not None
            },
            "_probe_http_status": result.get("_probe_http_status"),
            "_probe_transport": result.get("_probe_transport"),
        }
        turn["findings"] = _turn_flags(turn, spec.get("expect") or {})
        turns_out.append(turn)
        if pause_s > 0:
            time.sleep(pause_s)

    report = {
        "status": "success",
        "generated_at": _utc_stamp(),
        "scenario": scenario.get("name"),
        "description": scenario.get("description"),
        "transport": transport,
        "base_url": base_url,
        "model": model,
        "turn_count": len(turns_out),
        "turns": turns_out,
    }
    report["analysis"] = analyze_turns(turns_out)
    return report


def analyze_turns(turns: list[dict[str, Any]]) -> dict[str, Any]:
    all_findings: list[dict[str, Any]] = []
    for t in turns:
        findings = t.get("findings")
        if findings is None:
            findings = _turn_flags(t)
            t["findings"] = findings
        for f in findings:
            all_findings.append(
                {
                    **f,
                    "turn_id": t.get("id") or t.get("turn_id"),
                    "user_input": _clip(t.get("user_input"), 80),
                    "latency_ms": t.get("latency_ms"),
                    "action_type": t.get("action_type"),
                    "route": t.get("route"),
                    "model": t.get("actual_model"),
                }
            )

    by_sev = {"high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        by_sev[f.get("severity", "low")] = by_sev.get(f.get("severity", "low"), 0) + 1

    latencies = [int(t["latency_ms"]) for t in turns if t.get("latency_ms") is not None]
    summary = {
        "turns_analyzed": len(turns),
        "findings_total": len(all_findings),
        "by_severity": by_sev,
        "latency_ms": {
            "count": len(latencies),
            "max": max(latencies) if latencies else None,
            "avg": round(sum(latencies) / len(latencies)) if latencies else None,
        },
        "verdict": (
            "FAIL"
            if by_sev["high"]
            else ("WARN" if by_sev["medium"] else "PASS")
        ),
        "findings": all_findings,
    }
    return summary


def analyze_recorder(limit: int = 40, channel: str | None = None) -> dict[str, Any]:
    _ensure_backend_path()
    import database as db
    import json as _json

    turns = db.list_command_center_turns(limit=limit)
    normalized = []
    for t in turns:
        ch = str(t.get("channel") or "")
        if channel and ch != channel:
            continue
        trace = {}
        raw = t.get("trace_json")
        if raw:
            try:
                trace = _json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                trace = {"parse_error": True}
        normalized.append(
            {
                "id": t.get("id"),
                "created_at": t.get("created_at"),
                "channel": t.get("channel"),
                "user_input": t.get("user_input"),
                "assistant_reply": t.get("assistant_reply"),
                "intent": t.get("intent"),
                "route": t.get("route"),
                "action_type": t.get("action_type"),
                "actual_model": t.get("actual_model"),
                "latency_ms": t.get("latency_ms"),
                "blocked": t.get("blocked"),
                "block_reason": t.get("block_reason"),
                "trace": trace,
                "reached_interpreter": trace.get("reached_interpreter"),
                "reached_model": trace.get("reached_model"),
                "short_circuit_reason": trace.get("short_circuit_reason"),
                "pending_cleared_without_execute": trace.get("pending_cleared_without_execute"),
                "capsule_id": trace.get("capsule_id") or trace.get("capsule_id_resolved"),
                "action_packet_summary": trace.get("action_packet_summary"),
                "memory_save_status": trace.get("memory_save_status"),
                "memory_hits_count": trace.get("memory_hits_count"),
                "customer_history_source": trace.get("customer_history_source"),
                "blink_events": trace.get("blink_events"),
                "agent_loop_steps": trace.get("agent_loop_steps"),
                "factual_packet_digest": trace.get("factual_packet_digest"),
            }
        )
    return {
        "status": "success",
        "source": "command_center_recorder",
        "generated_at": _utc_stamp(),
        "channel_filter": channel,
        "turns": normalized,
        "analysis": analyze_turns(normalized),
    }


def analyze_report_file(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    turns = data.get("turns") or data.get("recent_turns") or []
    data["analysis"] = analyze_turns(turns)
    data["generated_at"] = _utc_stamp()
    return data


def _print_human_summary(report: dict[str, Any]) -> None:
    analysis = report.get("analysis") or {}
    print(f"verdict={analysis.get('verdict')} findings={analysis.get('findings_total')} "
          f"sev={analysis.get('by_severity')} latency={analysis.get('latency_ms')}")
    for t in report.get("turns") or []:
        print("----")
        print(f"[{t.get('id')}] lat={t.get('latency_ms')}ms action={t.get('action_type')} "
              f"route={t.get('route')} model={t.get('actual_model')}")
        print("IN :", _clip(t.get("user_input"), 160))
        print("OUT:", _clip(t.get("assistant_reply"), 220))
        for f in t.get("findings") or []:
            print(f"  ! {f.get('severity')}: {f.get('code')} — {f.get('detail')}")
    findings = analysis.get("findings") or []
    if findings and not report.get("turns"):
        for f in findings:
            print(f"! {f.get('severity')}: {f.get('code')} — {f.get('detail')} "
                  f"(in={f.get('user_input')})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Neena owner-like interaction probe + analyzer")
    parser.add_argument("command", choices=("run", "analyze", "probe"), help="Mode")
    parser.add_argument("--scenario", default="owner_smoke", help="Scenario pack name (JSON)")
    parser.add_argument("--mode", choices=("inprocess", "http"), default="inprocess")
    parser.add_argument("--base-url", default=os.environ.get("NEENA_PROBE_BASE_URL", ""))
    parser.add_argument("--cookie-file", default=os.environ.get("NEENA_PROBE_COOKIE_FILE", ""))
    parser.add_argument("--model", default="auto")
    parser.add_argument("--pause", type=float, default=0.4, help="Pause between turns (seconds)")
    parser.add_argument("--limit", type=int, default=40, help="Recorder turns for analyze")
    parser.add_argument("--channel", default="", help="Recorder channel prefix filter")
    parser.add_argument("--from-report", default="", help="Analyze an existing probe JSON")
    parser.add_argument("--out", default="", help="Write JSON report path")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else None
    if args.command in ("run", "probe") and out_path is None:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DEFAULT_OUT_DIR / f"probe_{args.scenario}_{_utc_stamp()}.json"

    report: dict[str, Any]
    if args.command == "analyze":
        if args.from_report:
            report = analyze_report_file(args.from_report)
        else:
            report = analyze_recorder(limit=args.limit, channel=args.channel or None)
    else:
        scenario = _load_scenario(args.scenario)
        report = run_scenario(
            scenario,
            transport=args.mode,
            base_url=args.base_url or None,
            cookie_file=args.cookie_file or None,
            model=args.model,
            pause_s=args.pause,
        )
        if args.command == "probe" and args.mode == "inprocess":
            # Also attach a short recorder snapshot when DB is available.
            try:
                snap = analyze_recorder(limit=min(20, args.limit), channel=None)
                report["recorder_snapshot"] = {
                    "verdict": (snap.get("analysis") or {}).get("verdict"),
                    "findings_total": (snap.get("analysis") or {}).get("findings_total"),
                    "by_severity": (snap.get("analysis") or {}).get("by_severity"),
                }
            except Exception as exc:
                report["recorder_snapshot"] = {"status": "skipped", "error": type(exc).__name__}

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"wrote {out_path}")

    if not args.quiet:
        _print_human_summary(report)

    verdict = ((report.get("analysis") or {}).get("verdict")) or "PASS"
    return 2 if verdict == "FAIL" else (1 if verdict == "WARN" else 0)


if __name__ == "__main__":
    # Silence unused-import style noise for optional regex helper kept for future packs.
    _ = re
    raise SystemExit(main())

#!/usr/bin/env python3
"""M4-A7 — Docker memory stack health report (no destructive actions)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(ROOT, "backend")
COMPOSE_FILE = os.path.join(ROOT, "docker-compose.memory.yml")
sys.path.insert(0, BACKEND)


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ROOT,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def docker_engine_running() -> bool:
    for cmd in (["docker", "version"], ["docker", "ps", "-q", "-n", "1"]):
        code, _ = _run(cmd, timeout=15)
        if code == 0:
            return True
    if container_running("neena-postgres") and container_running("neena-redis"):
        return True
    return False


def container_health(name: str) -> str:
    code, out = _run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", name],
        timeout=10,
    )
    if code != 0:
        return "missing"
    return out or "unknown"


def container_running(name: str) -> bool:
    code, out = _run(
        ["docker", "inspect", "--format", "{{.State.Running}}", name],
        timeout=10,
    )
    return code == 0 and out.lower() == "true"


def redis_aof_enabled() -> bool | None:
    if not container_running("neena-redis"):
        return None
    code, out = _run(["docker", "exec", "neena-redis", "redis-cli", "CONFIG", "GET", "appendonly"])
    if code != 0:
        return None
    parts = out.split()
    if len(parts) >= 2 and parts[-1].lower() in ("yes", "1", "on"):
        return True
    return False


def python_stack_checks() -> dict:
    try:
        from services.memory.pg_repository import is_pgvector_available, is_postgres_available
        from services.brain.redis_state import is_redis_available

        pg = is_postgres_available()
        pv = is_pgvector_available()
        rd = is_redis_available()
        return {
            "postgres_python": pg,
            "pgvector_python": pv,
            "redis_python": rd,
        }
    except Exception as exc:
        return {"error": type(exc).__name__}


def main() -> int:
    pg_running = container_running("neena-postgres")
    redis_running = container_running("neena-redis")
    engine = docker_engine_running()

    report: dict = {
        "docker_engine": engine,
        "compose_file": os.path.basename(COMPOSE_FILE),
        "containers": {
            "neena-postgres": {
                "running": pg_running,
                "health": container_health("neena-postgres"),
            },
            "neena-redis": {
                "running": redis_running,
                "health": container_health("neena-redis"),
                "aof": redis_aof_enabled(),
            },
        },
    }

    if pg_running and redis_running and not _run(["docker", "version"], timeout=10)[0] == 0:
        report["docker_engine_note"] = "inferred from healthy containers"

    stack_reachable = engine or (pg_running and redis_running)
    if stack_reachable:
        report["python_checks"] = python_stack_checks()
    else:
        report["python_checks"] = {"skipped": "docker engine not running"}
        report["recovery_command"] = (
            "Start Docker Desktop, then: docker compose -f docker-compose.memory.yml up -d"
        )

    pg_ok = report["containers"]["neena-postgres"]["health"] == "healthy"
    redis_ok = report["containers"]["neena-redis"]["health"] == "healthy"
    py = report.get("python_checks") or {}
    pgvector_active = bool((py.get("pgvector_python") or {}).get("available"))

    report["summary"] = {
        "memory_stack_healthy": bool(stack_reachable and pg_ok and redis_ok and pgvector_active),
        "postgres_healthy": pg_ok,
        "pgvector_active": pgvector_active,
        "redis_healthy": redis_ok,
        "redis_aof": report["containers"]["neena-redis"].get("aof"),
    }

    if not report["summary"]["memory_stack_healthy"]:
        report["recovery_command"] = (
            "docker compose -f docker-compose.memory.yml up -d"
        )

    print("Memory stack check (M4-A7)")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["summary"]["memory_stack_healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

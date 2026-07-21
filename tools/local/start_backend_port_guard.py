#!/usr/bin/env python3
"""Local-only guard: avoid duplicate uvicorn on 127.0.0.1:8000 (M3-A2)."""
from __future__ import annotations

import socket
import subprocess
import sys

HOST = "127.0.0.1"
PORT = 8000


def _pid_listening_on_port(host: str, port: int) -> int | None:
    """Return PID if something is listening on host:port (Windows netstat)."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        if local_addr.endswith(f":{port}") and (
            host in local_addr or local_addr.startswith(f"{host}:")
        ):
            try:
                return int(parts[-1])
            except ValueError:
                continue
    return None


def _socket_probe(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def main() -> int:
    pid = _pid_listening_on_port(HOST, PORT)
    listening = pid is not None or _socket_probe(HOST, PORT)

    if listening:
        pid_text = str(pid) if pid else "unknown"
        print(f"Backend already running on http://{HOST}:{PORT} (PID {pid_text})")
        print("Not starting duplicate server.")
        return 0

    print(f"Port {PORT} is free. Start backend manually, e.g.:")
    print(
        "  cd radio-ai-manager && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

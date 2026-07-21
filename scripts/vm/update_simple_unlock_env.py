#!/usr/bin/env python3
"""Update ADMIN_UNLOCK_* keys in .env without printing values."""
from __future__ import annotations

from pathlib import Path

UPDATES = {
    "ADMIN_UNLOCK_PHRASE": "hi neena i am vikram cool",
    "ADMIN_UNLOCK_MIN_SCORE": "0.70",
    "ADMIN_UNLOCK_REQUIRED_WORDS": "neena,vikram,cool",
}


def main() -> None:
    p = Path(".env")
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in UPDATES:
                out.append(f"{key}={UPDATES[key]}")
                seen.add(key)
            else:
                out.append(line)
        else:
            out.append(line)

    for key, value in UPDATES.items():
        if key not in seen:
            out.append(f"{key}={value}")

    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("unlock env updated")


if __name__ == "__main__":
    main()

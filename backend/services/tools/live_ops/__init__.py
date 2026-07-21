"""Live-ops hands package — bind category handlers onto catalog (ADR-013 Wave 2)."""
from __future__ import annotations


def bind_all() -> None:
    from services.tools.live_ops import (
        azura_pulse,
        capsules,
        memory_ops,
        recorder,
        status,
        stream_listener,
    )

    status.bind()
    azura_pulse.bind()
    stream_listener.bind()
    capsules.bind()
    recorder.bind()
    memory_ops.bind()


__all__ = ["bind_all"]

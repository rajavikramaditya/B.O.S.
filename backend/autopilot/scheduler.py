"""B.O.S. Autopilot Scheduler v1.0

Background thread that triggers proactive reviews on an interval, once the
workspace is ready (owner created, business profile filled, AI connected).
"""

import logging
import threading
from typing import Callable, Optional

from .engine import AutopilotEngine

logger = logging.getLogger("bos.autopilot")


class AutopilotScheduler:
    def __init__(self, interval_minutes: int, is_ready: Callable[[], bool], tick_seconds: int = 60):
        self.interval_minutes = interval_minutes
        self.is_ready = is_ready
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="bos-autopilot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # Short grace period so a fresh deploy doesn't fire a review mid-startup.
        if self._stop.wait(30):
            return
        while not self._stop.is_set():
            try:
                if self.is_ready() and AutopilotEngine.is_due(self.interval_minutes):
                    AutopilotEngine.run(trigger="schedule")
            except Exception:
                logger.exception("Autopilot tick failed")
            self._stop.wait(self.tick_seconds)

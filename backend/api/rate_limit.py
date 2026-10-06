"""B.O.S. Rate Limiter v1.0

Small in-process sliding-window limiter for sensitive endpoints (sign-in, setup).
"""

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait a minute.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        self.check(request.client.host if request.client else "unknown")


auth_limiter = RateLimiter(limit=8, window_seconds=60)
# Per-account limit on top of the per-address one, so rotating addresses can't spray one account.
account_limiter = RateLimiter(limit=10, window_seconds=300)


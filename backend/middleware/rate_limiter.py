"""
backend/middleware/rate_limiter.py
Per-thread sliding-window rate limiter (30 requests/min).

Applied only to POST /api/threads/{thread_id}/messages.
All other endpoints are unrestricted.

Implementation
--------------
Uses a sliding window (deque of timestamps) keyed by thread_id.
On every qualifying request:
  1. Pop timestamps older than `window_seconds` from the left.
  2. If deque length >= max_requests → 429 Too Many Requests.
  3. Otherwise → append current timestamp and allow.

Thread-safety: a single threading.Lock guards the timestamp dict.
The lock is held only during the deque inspection and append — well under 1ms.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ThreadRateLimiter(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter scoped to individual conversation threads.

    Only POST /api/threads/<id>/messages requests are counted.
    Returns HTTP 429 when a thread exceeds max_requests in window_seconds.
    """

    def __init__(
        self,
        app,
        *,
        max_requests:   int = 30,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _extract_thread_id(self, path: str) -> str | None:
        """
        Extract thread_id from a path like /api/threads/<uuid>/messages.
        Returns None if the path does not match that pattern.
        """
        parts = path.rstrip("/").split("/")
        try:
            idx = parts.index("threads")
            thread_id = parts[idx + 1]
            # Must be followed by "messages"
            if parts[idx + 2] == "messages":
                return thread_id
        except (ValueError, IndexError):
            pass
        return None

    async def dispatch(self, request: Request, call_next):
        # Rate limiting scope: POST .../messages only
        if request.method != "POST":
            return await call_next(request)

        thread_id = self._extract_thread_id(request.url.path)
        if thread_id is None:
            return await call_next(request)

        now = time.monotonic()

        with self._lock:
            window = self._windows[thread_id]

            # Evict timestamps outside the sliding window
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.max_requests:
                remaining_wait = int(self.window_seconds - (now - window[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Rate limit exceeded: {self.max_requests} requests "
                            f"per {self.window_seconds}s per thread. "
                            f"Retry after {remaining_wait}s."
                        ),
                        "retry_after_seconds": remaining_wait,
                    },
                    headers={"Retry-After": str(remaining_wait)},
                )

            window.append(now)

        return await call_next(request)

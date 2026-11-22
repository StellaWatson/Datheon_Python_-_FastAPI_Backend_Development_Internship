"""
In-memory sliding-window rate limiter, used as a FastAPI dependency.

Each limiter instance keeps its own bucket per client IP. This is fine for a
single Uvicorn process; with several workers/containers you would move the
counters to Redis so all instances share them.
"""
import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, scope: str):
        self.limit = limit
        self.window_seconds = window_seconds
        self.scope = scope
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    async def __call__(self, request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_ip]

        # Drop timestamps that fell out of the window.
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()

        if len(hits) >= self.limit:
            retry_after = math.ceil(self.window_seconds - (now - hits[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.scope}. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)}
            )

        hits.append(now)


# Strict limit for login/register (brute-force protection).
auth_rate_limiter = RateLimiter(
    limit=settings.AUTH_RATE_LIMIT,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    scope="auth"
)

# General limit for the rest of the API.
api_rate_limiter = RateLimiter(
    limit=settings.API_RATE_LIMIT,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    scope="api"
)

ALL_LIMITERS = (auth_rate_limiter, api_rate_limiter)

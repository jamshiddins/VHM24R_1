"""
Rate limiting middleware for VHM24R.

This middleware uses a Redis backend to track the number of requests
made by each client IP within a specified time window. If the number
of requests exceeds the configured limit, a HTTP 429 Too Many
Requests response is returned. The maximum number of requests and
window duration can be configured via environment variables or
parameters.
"""

import os
from typing import Callable

import redis
from fastapi import HTTPException, Request, Response


class RateLimiter:
    """Simple IP‑based rate limiter using Redis."""

    def __init__(self, redis_client: redis.Redis, max_requests: int = 100, window: int = 3600) -> None:
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        current = self.redis.get(key)
        if current is None:
            # First request: set TTL
            self.redis.setex(key, self.window, 1)
        else:
            current_int = int(current)
            if current_int >= self.max_requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            self.redis.incr(key)
        return await call_next(request)

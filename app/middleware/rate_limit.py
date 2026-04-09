"""Lazo Agent — Rate Limiting Middleware

Simple in-memory rate limiter. For production with multiple workers,
upgrade to Redis-backed rate limiting.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit by client IP. Default: 100 requests per minute."""

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health checks and WebSocket upgrades
        if request.url.path.startswith("/api/health") or request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - 60

        # Clean old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window
        ]

        if len(self._requests[client_ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)

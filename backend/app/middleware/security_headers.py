"""
Security headers middleware for VHM24R.

This middleware adds a number of HTTP security headers to every
response returned by the FastAPI application. These headers help
protect against common web vulnerabilities such as clickjacking,
MIME sniffing, XSS, and ensure strict transport security.
"""

from typing import Callable

from fastapi import Request, Response


class SecurityHeadersMiddleware:
    """Middleware that injects security headers into each response."""

    def __init__(self, app: Callable[[Request], Response]) -> None:
        self.app = app

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

"""
Prometheus metrics middleware for VHM24R.

This middleware records the number of HTTP requests and their
durations using Prometheus counters and histograms. It exposes
metrics that can be scraped by a Prometheus server for monitoring
purposes. The middleware should be added to the FastAPI application
during startup.
"""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram


# Define Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
)


class MetricsMiddleware:
    """Middleware that collects Prometheus metrics for each request."""

    def __init__(self, app: Callable[[Request], Response]) -> None:
        self.app = app

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        # Record metrics
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
        REQUEST_DURATION.observe(duration)
        return response

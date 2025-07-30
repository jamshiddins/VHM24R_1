"""
Custom logging setup for VHM24R.

This module configures structured logging using structlog. It should be
imported at application startup (e.g., in ``main.py``) to ensure all
subsequent loggers are configured correctly. See the project
documentation for guidance on configuring log levels and handlers in
production environments.
"""

import logging
from datetime import datetime

import structlog


def setup_logging() -> None:
    """Configure structlog and the standard logging module.

    The configuration uses ISO‑8601 timestamps and outputs logs to
    standard output. In production, the underlying structlog
    configuration can be extended to emit JSON or forward logs to a
    centralized log collector.

    This function must be called once during application startup.
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

"""
Centralized error handling middleware for VHM24R.

This middleware intercepts unhandled exceptions bubbling up from the
FastAPI application and converts them into structured HTTP responses.
It also logs errors using the configured structlog logger. Custom
exceptions defined in ``utils.exceptions`` are mapped to specific
HTTP status codes. All other exceptions result in a generic 500
Internal Server Error response.
"""

import logging
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from ..utils.exceptions import (
    VHMException,
    AuthenticationError,
    AuthorizationError,
    FileProcessingError,
    DatabaseError,
)


class ErrorHandlerMiddleware:
    """Middleware for handling exceptions and producing structured responses."""

    def __init__(self, app: Callable[[Request], Any]) -> None:
        self.app = app
        self.logger = logging.getLogger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except AuthenticationError as exc:
            self.logger.warning("Authentication error", exc_info=exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized", "error": str(exc)},
            )
        except AuthorizationError as exc:
            self.logger.warning("Authorization error", exc_info=exc)
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden", "error": str(exc)},
            )
        except FileProcessingError as exc:
            self.logger.error("File processing error", exc_info=exc)
            return JSONResponse(
                status_code=400,
                content={"detail": "File processing failed", "error": str(exc)},
            )
        except DatabaseError as exc:
            self.logger.error("Database error", exc_info=exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Database error", "error": str(exc)},
            )
        except VHMException as exc:
            # Generic application error
            self.logger.error("Application error", exc_info=exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": str(exc)},
            )
        except Exception as exc:
            # Unknown error
            self.logger.exception("Unhandled exception", exc_info=exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": "Unexpected error"},
            )

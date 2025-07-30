"""
Custom exception classes for VHM24R.

These exceptions allow the application to distinguish between different
error conditions and return appropriate HTTP responses while
maintaining a clean separation between business logic and API
transport. All custom exceptions should inherit from
``VHMException``.
"""


class VHMException(Exception):
    """Base exception for VHM24R.

    Any exception that originates from within the VHM24R domain should
    derive from this class. This makes it easier to implement common
    error handling logic and ensures a consistent hierarchy of
    exception types.
    """


class AuthenticationError(VHMException):
    """Raised when authentication fails.

    This exception indicates that the provided credentials or tokens
    were invalid or expired. API handlers should catch this
    exception and return an HTTP 401 Unauthorized response.
    """


class AuthorizationError(VHMException):
    """Raised when a user attempts an action they are not allowed to perform."""


class FileProcessingError(VHMException):
    """Raised when the system encounters an error during file processing."""


class DatabaseError(VHMException):
    """Raised when database operations fail or return unexpected results."""

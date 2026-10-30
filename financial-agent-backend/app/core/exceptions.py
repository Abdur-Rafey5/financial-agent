"""
Application-wide exception hierarchy.

All custom exceptions inherit from AppException so they can be caught
by a single error handler in the FastAPI app.
"""

from typing import Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = 500,
        detail: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class AuthenticationError(AppException):
    """Invalid credentials or expired token."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(AppException):
    """User lacks permission for the requested operation."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message=message, status_code=403)


class NotFoundError(AppException):
    """Requested resource does not exist or is not owned by the user."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(message=msg, status_code=404)


class ConflictError(AppException):
    """Duplicate or conflicting resource."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message=message, status_code=409)


class ValidationError(AppException):
    """Domain-level validation failure (not Pydantic schema validation)."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message=message, status_code=422)


class ExternalServiceError(AppException):
    """Failure communicating with an external service (LLM, market data)."""

    def __init__(self, service: str, message: str = ""):
        msg = f"External service error: {service}"
        if message:
            msg += f" — {message}"
        super().__init__(message=msg, status_code=502)


class RateLimitError(AppException):
    """Too many requests."""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message=message, status_code=429)

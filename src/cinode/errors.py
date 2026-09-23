"""The exceptions the library raises. Every one of them is a `CinodeError`."""

from typing import Any

FORBIDDEN_HINT = (
    "Cinode refused access. Every request runs as the user who owns the API account, "
    "so the client can read only what that user can read in Cinode. A 403 for one "
    "person's data while others succeed is normal, not a fault in the client."
)


class CinodeError(Exception):
    """Base class for every error from the Cinode client."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        path: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.path = path
        self.correlation_id = correlation_id

    def to_dict(self) -> dict[str, Any]:
        """The error as a JSON-ready dict, as the CLI writes it to stderr."""
        return {
            "type": type(self).__name__,
            "status": self.status,
            "path": self.path,
            "message": self.message,
            "correlation_id": self.correlation_id,
        }


class AuthError(CinodeError):
    """Missing or rejected credentials, or a 401 that survived a token refresh."""


class ForbiddenError(CinodeError):
    """A 403: the account owner may not read this data."""


class NotFoundError(CinodeError):
    """A 404."""


class RateLimitedError(CinodeError):
    """A 429 that outlasted every retry."""


class BadRequestError(CinodeError):
    """A 400, with Cinode's per-field messages in `field_errors`."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        path: str | None = None,
        correlation_id: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(message, status=status, path=path, correlation_id=correlation_id)
        self.field_errors: dict[str, list[str]] = field_errors or {}

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "field_errors": self.field_errors}


class ServerError(CinodeError):
    """A 5xx that outlasted every retry."""


class UnexpectedResponseError(CinodeError):
    """A response body that is not JSON, or does not fit the model."""

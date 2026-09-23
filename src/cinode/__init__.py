"""A read-only client for the Cinode API."""

from cinode._client import Cinode
from cinode._version import __version__
from cinode.errors import (
    AuthError,
    BadRequestError,
    CinodeError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    UnexpectedResponseError,
)
from cinode.resources import UserRef

__all__ = [
    "AuthError",
    "BadRequestError",
    "Cinode",
    "CinodeError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitedError",
    "ServerError",
    "UnexpectedResponseError",
    "UserRef",
    "__version__",
]

"""Token exchange, JWT claims and expiry."""

import base64
import binascii
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

import httpx

from cinode._ratelimit import RateLimiter
from cinode.errors import AuthError, CinodeError, RateLimitedError, UnexpectedResponseError

TOKEN_PATH = "/token"
DEFAULT_LIFETIME = 120.0
REFRESH_MARGIN = 30.0


@dataclass(frozen=True)
class Token:
    """An access token and the claims the client routes by.

    `expires_at` is on the local clock (the `now` the manager was given), not
    Cinode's. `value` is kept out of `repr`.
    """

    value: str = field(repr=False)
    user_id: int
    company_id: int
    expires_at: float


def decode_token(jwt: str, *, issued_at: float) -> Token:
    """Read a JWT's claims without checking its signature.

    The lifetime is `exp - iat`, or 120 s if either is missing or the
    difference is not a finite positive number. It is counted from `issued_at`
    on the local clock. That way a local clock out of step with Cinode's does
    not make every token look expired.
    """
    parts = jwt.split(".")
    if len(parts) < 2:
        raise _malformed("it is not a JWT")
    payload = parts[1]
    try:
        decoded: Any = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError, binascii.Error:
        raise _malformed("its payload is not base64url-encoded JSON") from None
    if not isinstance(decoded, dict):
        raise _malformed("its payload is not a JSON object")
    claims = cast(dict[str, Any], decoded)
    ids: dict[str, int] = {}
    for claim in ("sub", "companySub"):
        if claim not in claims:
            raise _malformed(f"its payload is missing claim '{claim}'")
        try:
            ids[claim] = int(claims[claim])
        except TypeError, ValueError:
            raise _malformed(f"claim '{claim}' is not an integer") from None
    iat, exp = claims.get("iat"), claims.get("exp")
    try:
        lifetime = float(exp) - float(iat) if iat is not None and exp is not None else None
    except TypeError, ValueError:
        raise _malformed("claim 'iat' or 'exp' is not a number") from None
    if lifetime is None or not math.isfinite(lifetime) or lifetime <= 0:
        lifetime = DEFAULT_LIFETIME
    return Token(
        value=jwt,
        user_id=ids["sub"],
        company_id=ids["companySub"],
        expires_at=issued_at + lifetime,
    )


def _malformed(reason: str) -> UnexpectedResponseError:
    return UnexpectedResponseError(f"Cinode returned a malformed token: {reason}.", path=TOKEN_PATH)


class TokenManager:
    """Fetch a token with the Basic credential, cache it, and refresh it near expiry."""

    def __init__(
        self,
        http: httpx.Client,
        basic: str,
        limiter: RateLimiter,
        *,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._http = http
        self._basic = basic
        self._limiter = limiter
        self._now = now
        self._token: Token | None = None

    def get(self) -> Token:
        """The cached token, or a new one if less than 30 s of its lifetime remain."""
        token = self._token
        if token is None or token.expires_at - self._now() < REFRESH_MARGIN:
            token = self._token = self._fetch()
        return token

    def invalidate(self) -> None:
        """Drop the cached token, so the next `get()` fetches a new one."""
        self._token = None

    def _fetch(self) -> Token:
        self._limiter.acquire()
        response = self._http.get(TOKEN_PATH, headers={"Authorization": f"Basic {self._basic}"})
        status = response.status_code
        if status in (400, 401, 403):
            raise AuthError("Cinode rejected the API credentials.", status=status, path=TOKEN_PATH)
        if status == 429:
            raise RateLimitedError(
                "Cinode rate-limited the token exchange.", status=status, path=TOKEN_PATH
            )
        if status >= 400:
            raise CinodeError(
                f"The token exchange failed with HTTP {status}.", status=status, path=TOKEN_PATH
            )
        issued_at = self._now()
        try:
            body: Any = response.json()
            jwt = body["access_token"]
            if not isinstance(jwt, str):
                raise TypeError
        except ValueError, KeyError, TypeError:
            raise UnexpectedResponseError(
                "Cinode's token response has no access_token.", status=status, path=TOKEN_PATH
            ) from None
        return decode_token(jwt, issued_at=issued_at)

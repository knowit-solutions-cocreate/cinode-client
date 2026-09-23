"""The GET-only transport: tokens, rate limits, retries and error mapping."""

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NoReturn, cast

import httpx

from cinode._auth import TOKEN_PATH, Token, TokenManager
from cinode._config import Settings
from cinode._ratelimit import RateLimiter, retry_after
from cinode._version import __version__
from cinode.errors import (
    FORBIDDEN_HINT,
    AuthError,
    BadRequestError,
    CinodeError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    UnexpectedResponseError,
)

API_PREFIX = "/v0.1/"

RATE_LIMIT_ATTEMPTS = 5
SERVER_ATTEMPTS = 3
RETRY_STATUSES = frozenset({502, 503, 504})
MAX_BACKOFF = 8.0


@dataclass
class _Attempts:
    """The failures one call has retried so far."""

    rate_limited: int = 0
    failed: int = 0


class Transport:
    """The only way to reach Cinode. It can issue GET and nothing else.

    Every call is a GET, so every retry is safe: a 401 refreshes the token and
    retries once, a 429 is retried up to 5 attempts, and 502/503/504 or a
    network error up to 3. The token fetch counts as part of the attempt, so
    its network errors, 429s and 5xx are retried the same way.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._sleep = sleep
        self._rng = rng
        self._http = httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": f"cinode-client/{__version__}",
            },
        )
        self._limiter = RateLimiter(40, 2.0, clock=clock, sleep=sleep)
        self.tokens = TokenManager(
            self._http, settings.basic, RateLimiter(2, 2.0, clock=clock, sleep=sleep), now=now
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def token(self) -> Token:
        """The current token, fetched under the same retries and error mapping as `get()`."""
        self._check_open(TOKEN_PATH)
        attempts = _Attempts()
        while True:
            try:
                return self.tokens.get()
            except (httpx.RequestError, RateLimitedError, ServerError) as exc:
                self._recover(exc, attempts, TOKEN_PATH)

    def get(self, path: str, *, versioned: bool = True) -> Any:
        """GET `path` under `/v0.1/`, or under `/` when `versioned` is False.

        Returns the decoded JSON body, or None for an empty body.
        """
        url = (API_PREFIX if versioned else "/") + path.lstrip("/")
        self._check_open(url)
        attempts = _Attempts()
        refreshed = False
        while True:
            target = TOKEN_PATH
            try:
                token = self.tokens.get()
                target = url
                self._limiter.acquire()
                response = self._http.get(url, headers={"Authorization": f"Bearer {token.value}"})
            except (httpx.RequestError, RateLimitedError, ServerError) as exc:
                self._recover(exc, attempts, target)
                continue

            status = response.status_code
            if status == 401 and not refreshed:
                refreshed = True
                self.tokens.invalidate()
                continue
            if status == 429:
                attempts.rate_limited += 1
                if attempts.rate_limited < RATE_LIMIT_ATTEMPTS:
                    self._sleep(
                        retry_after(response.headers.get("Retry-After"))
                        or self._backoff(attempts.rate_limited)
                    )
                    continue
            elif status in RETRY_STATUSES:
                attempts.failed += 1
                if attempts.failed < SERVER_ATTEMPTS:
                    self._sleep(self._backoff(attempts.failed))
                    continue
            if not response.is_success:
                _raise_for_status(response, url)
            return _json(response, url)

    def _check_open(self, path: str) -> None:
        if self._http.is_closed:
            raise CinodeError("The transport has been closed.", path=path)

    def _recover(
        self,
        exc: httpx.RequestError | RateLimitedError | ServerError,
        attempts: _Attempts,
        target: str,
    ) -> None:
        """Sleep before the next attempt after `exc`, or raise if it is not to be retried."""
        if isinstance(exc, httpx.TransportError):
            attempts.failed += 1
            if attempts.failed >= SERVER_ATTEMPTS:
                raise CinodeError(
                    f"Could not reach Cinode: {exc.__class__.__name__}.", path=target
                ) from exc
            self._sleep(self._backoff(attempts.failed))
        elif isinstance(exc, httpx.RequestError):
            raise CinodeError(
                f"The request to Cinode failed: {exc.__class__.__name__}.", path=target
            ) from exc
        elif isinstance(exc, RateLimitedError):
            attempts.rate_limited += 1
            if attempts.rate_limited >= RATE_LIMIT_ATTEMPTS:
                raise exc
            self._sleep(exc.retry_after or self._backoff(attempts.rate_limited))
        else:
            attempts.failed += 1
            if exc.status not in RETRY_STATUSES or attempts.failed >= SERVER_ATTEMPTS:
                raise exc
            self._sleep(self._backoff(attempts.failed))

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff for the `attempt`-th failure (from 1), with jitter."""
        return min(MAX_BACKOFF, 0.5 * 2 ** (attempt - 1)) * (0.5 + self._rng() / 2)


def _correlation_id(response: httpx.Response) -> str | None:
    for name, value in response.headers.items():
        if "correlation" in name.lower():
            return value
    return None


def _json(response: httpx.Response, path: str) -> Any:
    if not response.content.strip():
        return None
    try:
        return response.json()
    except ValueError:
        raise UnexpectedResponseError(
            f"Cinode returned a body that is not JSON (HTTP {response.status_code}).",
            status=response.status_code,
            path=path,
            correlation_id=_correlation_id(response),
        ) from None


def _field_errors(response: httpx.Response) -> dict[str, list[str]]:
    """Cinode's `{"errors": {field: [message, ...]}}`, or {} for any other body."""
    try:
        body: Any = response.json()
    except ValueError:
        return {}
    if not isinstance(body, dict):
        return {}
    errors: Any = cast(dict[str, Any], body).get("errors")
    if not isinstance(errors, dict):
        return {}
    result: dict[str, list[str]] = {}
    for field, messages in cast(dict[str, Any], errors).items():
        if isinstance(messages, list):
            result[field] = [str(m) for m in cast(list[Any], messages)]
        else:
            result[field] = [str(messages)]
    return result


def _raise_for_status(response: httpx.Response, path: str) -> NoReturn:
    status = response.status_code
    common: dict[str, Any] = {
        "status": status,
        "path": path,
        "correlation_id": _correlation_id(response),
    }
    if status == 400:
        raise BadRequestError(
            "Cinode rejected the request as invalid.",
            field_errors=_field_errors(response),
            **common,
        )
    if status == 401:
        raise AuthError("Cinode rejected the access token after a refresh.", **common)
    if status == 403:
        raise ForbiddenError(FORBIDDEN_HINT, **common)
    if status == 404:
        raise NotFoundError(f"Cinode has nothing at {path}.", **common)
    if status == 429:
        raise RateLimitedError(
            "Cinode is still rate-limiting after every retry.",
            retry_after=retry_after(response.headers.get("Retry-After")),
            **common,
        )
    if status >= 500:
        raise ServerError(f"Cinode failed with HTTP {status}.", **common)
    raise CinodeError(f"Cinode answered HTTP {status}.", **common)

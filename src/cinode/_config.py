"""Credentials and settings, from arguments or the environment."""

import base64
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self

from cinode.errors import AuthError, CinodeError

DEFAULT_BASE_URL = "https://api.cinode.com"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Settings:
    """What the transport needs: the Basic credential, the base URL and a timeout.

    `basic` is `base64(access_id:access_secret)`. It is kept out of `repr`.
    """

    basic: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_credentials(
        cls,
        access_id: str,
        access_secret: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Self:
        basic = base64.b64encode(f"{access_id}:{access_secret}".encode()).decode("ascii")
        return cls(basic=basic, base_url=base_url.rstrip("/"), timeout=timeout)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        """Read settings from `env`, or from `os.environ` when it is None.

        `CINODE_ACCESS_ID` and `CINODE_ACCESS_SECRET` win over `CINODE_BASIC`.
        Setting only one of the pair is an error, even when `CINODE_BASIC` is set.
        """
        env = os.environ if env is None else env
        base_url = (env.get("CINODE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        timeout = _timeout(env.get("CINODE_TIMEOUT"))

        access_id = env.get("CINODE_ACCESS_ID")
        access_secret = env.get("CINODE_ACCESS_SECRET")
        if access_id and access_secret:
            return cls.from_credentials(
                access_id, access_secret, base_url=base_url, timeout=timeout
            )
        if access_id or access_secret:
            missing = "CINODE_ACCESS_SECRET" if access_id else "CINODE_ACCESS_ID"
            raise AuthError(
                f"{missing} is not set. Set both CINODE_ACCESS_ID and CINODE_ACCESS_SECRET."
            )

        # GNU base64 wraps its output at 76 characters, so a pasted value may
        # hold newlines. Whitespace is never part of base64, so drop all of it.
        basic = "".join((env.get("CINODE_BASIC") or "").split())
        if basic:
            return cls(basic=basic, base_url=base_url, timeout=timeout)

        raise AuthError(
            "No Cinode credentials. Set CINODE_ACCESS_ID and CINODE_ACCESS_SECRET, "
            "or CINODE_BASIC to base64(access_id:access_secret)."
        )


def _timeout(value: str | None) -> float:
    if not value:
        return DEFAULT_TIMEOUT
    try:
        timeout = float(value)
    except ValueError:
        timeout = math.nan
    if not (math.isfinite(timeout) and timeout > 0):
        raise CinodeError(f"CINODE_TIMEOUT must be a positive number of seconds, not {value!r}.")
    return timeout

"""Credentials and settings, from arguments, the environment or the credentials file."""

import base64
import binascii
import contextlib
import dataclasses
import math
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Self

from cinode.errors import AuthError, CinodeError

DEFAULT_BASE_URL = "https://api.cinode.com"
DEFAULT_TIMEOUT = 30.0

type Source = Literal["argument", "env", "file"]

_FILE_KEYS = ("access_id", "access_secret")


def credentials_path(env: Mapping[str, str] | None = None) -> Path:
    """Where the credentials file is, whether or not it exists.

    `$CINODE_CREDENTIALS_FILE` (with `~` expanded), else
    `$XDG_CONFIG_HOME/cinode/credentials.toml` when that is absolute, else
    `~/.config/cinode/credentials.toml`. The home directory is `Path.home()`.
    """
    env = os.environ if env is None else env
    explicit = env.get("CINODE_CREDENTIALS_FILE")
    if explicit:
        return Path(explicit).expanduser()
    xdg = env.get("XDG_CONFIG_HOME")
    config_home = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return config_home / "cinode" / "credentials.toml"


def read_credentials(path: Path) -> tuple[str, str] | None:
    """`(access_id, access_secret)` from the credentials file, or None without one.

    Raises `AuthError` for a file that cannot be read, is not TOML, or lacks
    either key as a non-empty string. The message names the path and the key,
    never a value, so no parser message (which may quote a line) is passed on.
    """
    try:
        data = path.read_bytes()
    except FileNotFoundError, NotADirectoryError:
        return None
    except OSError:
        raise AuthError(f"Cannot read the credentials file at {path}.") from None

    # Parse outside any `except` block, so the parser's error, which can quote
    # the secret's line, is not even attached as context to the one raised here.
    document: dict[str, object] | None = None
    with contextlib.suppress(UnicodeDecodeError, tomllib.TOMLDecodeError):
        document = tomllib.loads(data.decode("utf-8"))
    if document is None:
        raise AuthError(f"The credentials file at {path} is not valid UTF-8 TOML.")

    values: list[str] = []
    for key in _FILE_KEYS:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise AuthError(
                f"The credentials file at {path} has no {key}; it must be a non-empty string."
            )
        values.append(value)
    return values[0], values[1]


def decode_basic(basic: str) -> tuple[str, str] | None:
    """`(access_id, access_secret)` from a `CINODE_BASIC` value, or None if it does not decode.

    Whitespace is dropped first, and the decoded text is split at its first `:`,
    since a secret may contain colons.
    """
    compact = "".join(basic.split())
    try:
        decoded = base64.b64decode(compact, validate=True).decode("utf-8")
    except binascii.Error, ValueError:  # ValueError covers non-ASCII and UnicodeDecodeError
        return None
    access_id, colon, access_secret = decoded.partition(":")
    if not colon:
        return None
    return access_id, access_secret


def env_options(env: Mapping[str, str]) -> tuple[str, float]:
    """The base URL and timeout from `CINODE_BASE_URL` and `CINODE_TIMEOUT`, or the defaults."""
    return _env_base_url(env), _timeout(env.get("CINODE_TIMEOUT"))


def _env_base_url(env: Mapping[str, str]) -> str:
    return (env.get("CINODE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


@dataclass(frozen=True)
class Settings:
    """What the transport needs: the Basic credential, the base URL and a timeout.

    `basic` is `base64(access_id:access_secret)`. It is kept out of `repr`.
    `source` says where the credentials came from, and `access_id` is the
    AccessId in use, when known. Neither is secret.
    """

    basic: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    source: Source = "argument"
    access_id: str | None = None

    @classmethod
    def from_credentials(
        cls,
        access_id: str,
        access_secret: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        source: Source = "argument",
    ) -> Self:
        basic = base64.b64encode(f"{access_id}:{access_secret}".encode()).decode("ascii")
        return cls(
            basic=basic,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            source=source,
            access_id=access_id,
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        """Read settings from `env`, or from `os.environ` when it is None.

        `CINODE_ACCESS_ID` and `CINODE_ACCESS_SECRET` win over `CINODE_BASIC`.
        Setting only one of the pair is an error, even when `CINODE_BASIC` is set.
        """
        env = os.environ if env is None else env
        base_url, timeout = env_options(env)

        access_id = env.get("CINODE_ACCESS_ID")
        access_secret = env.get("CINODE_ACCESS_SECRET")
        if access_id and access_secret:
            return cls.from_credentials(
                access_id, access_secret, base_url=base_url, timeout=timeout, source="env"
            )
        if access_id or access_secret:
            missing = "CINODE_ACCESS_SECRET" if access_id else "CINODE_ACCESS_ID"
            raise AuthError(
                f"{missing} is not set. Set both CINODE_ACCESS_ID and CINODE_ACCESS_SECRET."
            )

        basic = _env_basic(env)
        if basic:
            decoded = decode_basic(basic)
            return cls(
                basic=basic,
                base_url=base_url,
                timeout=timeout,
                source="env",
                access_id=decoded[0] if decoded else None,
            )

        raise AuthError(
            "No Cinode credentials. Set CINODE_ACCESS_ID and CINODE_ACCESS_SECRET, "
            "or CINODE_BASIC to base64(access_id:access_secret)."
        )

    @classmethod
    def resolve(
        cls,
        access_id: str | None = None,
        access_secret: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
        credentials_file: Path | None = None,
    ) -> Self:
        """Settings from the arguments, else the environment, else the credentials file.

        The environment wins over the file as a whole: when it holds any
        credentials, even half a pair, the file is not opened. `base_url` and
        `timeout` fall back to the environment, then the defaults, whatever
        the credentials' source. With credentials from the arguments or the
        file, each is read from the environment only when its argument is
        missing; `from_env` reads both whenever it is used.
        """
        env = os.environ if env is None else env
        if (access_id is None) != (access_secret is None):
            raise ValueError("Pass both access_id and access_secret, or neither.")
        base_url = _env_base_url(env) if base_url is None else base_url.rstrip("/")
        if timeout is None:
            timeout = _timeout(env.get("CINODE_TIMEOUT"))

        if access_id is not None and access_secret is not None:
            return cls.from_credentials(
                access_id, access_secret, base_url=base_url, timeout=timeout
            )

        if _env_holds_credentials(env):
            return dataclasses.replace(cls.from_env(env), base_url=base_url, timeout=timeout)

        path = credentials_file or credentials_path(env)
        credentials = read_credentials(path)
        if credentials is None:
            raise AuthError(
                f"No Cinode credentials: none in the environment, and no file at {path}. "
                "Run `cinode init`, or set CINODE_ACCESS_ID and CINODE_ACCESS_SECRET, "
                "or CINODE_BASIC to base64(access_id:access_secret)."
            )
        return cls.from_credentials(*credentials, base_url=base_url, timeout=timeout, source="file")


def _env_basic(env: Mapping[str, str]) -> str:
    # GNU base64 wraps its output at 76 characters, so a pasted value may
    # hold newlines. Whitespace is never part of base64, so drop all of it.
    return "".join((env.get("CINODE_BASIC") or "").split())


def _env_holds_credentials(env: Mapping[str, str]) -> bool:
    """`from_env`'s own test: any of the pair, or a `CINODE_BASIC` that is not blank."""
    return bool(env.get("CINODE_ACCESS_ID") or env.get("CINODE_ACCESS_SECRET") or _env_basic(env))


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

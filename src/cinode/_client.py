"""`Cinode`: construction, identity and resource wiring."""

from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Self

from cinode._config import Settings
from cinode._transport import Transport
from cinode.models import WhoAmI
from cinode.resources._base import Context
from cinode.resources.keywords import Keywords
from cinode.resources.teams import Teams
from cinode.resources.users import Users

WHOAMI_PATH = "/_whoami"


class Cinode:
    """A read-only Cinode client. Use it as a context manager, or call `close()`."""

    users: Users
    teams: Teams
    keywords: Keywords

    def __init__(
        self,
        access_id: str | None = None,
        access_secret: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
        credentials_file: Path | None = None,
    ) -> None:
        """A client with credentials from the arguments, else the environment, else the file.

        Pass both `access_id` and `access_secret`, or neither. `env` stands in
        for `os.environ`, and `credentials_file` for the file's default location.
        Raises `AuthError` when no credentials are found.
        """
        settings = Settings.resolve(
            access_id,
            access_secret,
            base_url=base_url,
            timeout=timeout,
            env=env,
            credentials_file=credentials_file,
        )
        self._wire(Transport(settings))

    @classmethod
    def _with_transport(cls, transport: Transport) -> Self:
        """A client over an existing transport. For tests."""
        client = cls.__new__(cls)
        client._wire(transport)
        return client

    def _wire(self, transport: Transport) -> None:
        self._transport = transport
        self._ctx = Context(transport)
        self.users = Users(self._ctx)
        self.teams = Teams(self._ctx)
        self.keywords = Keywords(self._ctx)

    @property
    def company_id(self) -> int:
        """The company id, from the token."""
        return self._ctx.company_id

    def whoami(self) -> WhoAmI:
        """The account owner's company and user ids, from `/_whoami`."""
        return WhoAmI.parse(self._transport.get(WHOAMI_PATH, versioned=False), path=WHOAMI_PATH)

    def close(self) -> None:
        """Close the HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

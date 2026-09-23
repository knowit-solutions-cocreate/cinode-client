"""`Cinode`: construction, identity and resource wiring."""

from collections.abc import Mapping
from types import TracebackType
from typing import Self

from cinode._config import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, Settings
from cinode._transport import Transport
from cinode.models import WhoAmI
from cinode.resources import Context, Users

WHOAMI_PATH = "/_whoami"


class Cinode:
    """A read-only Cinode client. Use it as a context manager, or call `close()`."""

    users: Users

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        settings = Settings.from_credentials(
            access_id, access_secret, base_url=base_url, timeout=timeout
        )
        self._wire(Transport(settings))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        """A client configured from `env`, or from `os.environ` when it is None."""
        return cls._with_transport(Transport(Settings.from_env(env)))

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
